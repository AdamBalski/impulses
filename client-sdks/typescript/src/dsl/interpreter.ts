import { ImpulsesClient } from "../client.js";
import { Datapoint, DatapointSeries } from "../models.js";
import { composeImpulses } from "../operations.js";
import { parse, AstNode, AstList } from "./parser.js";
import { DAY_MS, parseDuration, startOfDay } from "../internal/utils.js";
import {
  EnvironmentRef,
  FunctionValue,
  LambdaFunctionValue,
  NativeFunctionValue,
  Value,
  expectDatapoint,
  expectFunction,
  expectNumber,
  expectNumberArray,
  expectSeries,
  expectString,
  isFunctionValue,
  isLambdaFunction,
  isNativeFunction,
  isSeries,
  isSymbol,
  truthy,
} from "./types.js";

export type StreamResolver = (name: string) => Promise<DatapointSeries> | DatapointSeries;

class Environment implements EnvironmentRef {
  private readonly values = new Map<string, Value>();

  constructor(private readonly parent?: EnvironmentRef) {}

  define(name: string, value: Value) {
    this.values.set(name, value);
  }

  assign(name: string, value: Value) {
    if (this.values.has(name)) {
      this.values.set(name, value);
      return;
    }
    if (this.parent) {
      this.parent.assign(name, value);
      return;
    }
    throw new Error(`Undefined symbol '${name}'`);
  }

  lookup(name: string): Value {
    if (this.values.has(name)) {
      return this.values.get(name)!;
    }
    if (this.parent) {
      return this.parent.lookup(name);
    }
    throw new Error(`Undefined symbol '${name}'`);
  }

  snapshot(): Record<string, Value> {
    const record: Record<string, Value> = {};
    for (const [key, value] of this.values.entries()) {
      record[key] = value;
    }
    return record;
  }
}

class DslRuntime {
  private readonly builtinsEnv: Environment;
  private readonly globalEnv: Environment;
  private readonly resolverCache = new Map<string, DatapointSeries>();

  constructor(private readonly resolver: StreamResolver) {
    this.builtinsEnv = new Environment();
    this.registerBuiltins();
    this.globalEnv = new Environment(this.builtinsEnv);
  }

  async evaluate(source: string): Promise<Record<string, Value>> {
    const nodes = parse(source);
    for (const node of nodes) {
      await this.evalNode(node, this.globalEnv);
    }
    return this.globalEnv.snapshot();
  }

  private async evalNode(node: AstNode, env: Environment): Promise<Value> {
    switch (node.type) {
      case "number":
        return node.value;
      case "string":
        return node.value;
      case "symbol":
        return env.lookup(node.name);
      case "list":
        return this.evalList(node, env);
    }
  }

  private async evalList(list: AstList, env: Environment): Promise<Value> {
    if (list.items.length === 0) {
      return [];
    }

    const head = list.items[0];
    if (isSymbol(head, "define")) {
      const nameNode = list.items[1];
      if (!nameNode || nameNode.type !== "symbol") {
        throw new Error("define expects a symbol name");
      }
      const valueNode = list.items[2];
      if (!valueNode) {
        throw new Error("define missing value expression");
      }
      const value = await this.evalNode(valueNode, env);
      env.define(nameNode.name, value);
      return value;
    }

    if (isSymbol(head, "lambda")) {
      const paramsNode = list.items[1];
      if (!paramsNode || paramsNode.type !== "list") {
        throw new Error("lambda expects a parameter list");
      }
      const params = paramsNode.items.map((item): string => {
        if (item.type !== "symbol") {
          throw new Error("lambda parameter must be a symbol");
        }
        return item.name;
      });
      const body = list.items.slice(2);
      const lambdaValue: LambdaFunctionValue = {
        kind: "lambda",
        params,
        body,
        env,
      };
      return lambdaValue;
    }

    const fn = await this.evalNode(head, env);
    const args: Value[] = [];
    for (let i = 1; i < list.items.length; i += 1) {
      args.push(await this.evalNode(list.items[i], env));
    }
    return this.callFunction(fn, args);
  }

  private async callFunction(fn: Value, args: Value[]): Promise<Value> {
    if (!isFunctionValue(fn)) {
      throw new Error("Attempted to call non-function value");
    }
    if (isNativeFunction(fn)) {
      return fn.impl(...args);
    }
    if (!isLambdaFunction(fn)) {
      throw new Error("Unknown function value");
    }
    const scope = new Environment(fn.env);
    fn.params.forEach((param: string, idx: number) => {
      scope.define(param, args[idx]);
    });
    let result: Value = 0;
    for (const expr of fn.body) {
      result = await this.evalNode(expr, scope);
    }
    return result;
  }

  private registerBuiltins() {
    this.defineNative("data", async (name) => {
      const metricName = expectString(name);
      if (!this.resolverCache.has(metricName)) {
        const stream = await this.resolver(metricName);
        this.resolverCache.set(metricName, stream);
      }
      return this.resolverCache.get(metricName)!;
    });

    this.defineNative("window", (seriesValue, durationValue, aggregateValue) => {
      const series = expectSeries(seriesValue);
      const duration = parseDuration(expectString(durationValue));
      const aggregateFn = expectFunction(aggregateValue);
      return series.slidingWindow(duration, async (values) => {
        const result = await this.callFunction(aggregateFn, [values]);
        return expectNumber(result);
      });
    });

    this.defineNative("prefix", (seriesValue, aggregateValue) => {
      const series = expectSeries(seriesValue);
      const aggregateFn = expectFunction(aggregateValue);
      return series.prefixOp(async (values) => {
        const result = await this.callFunction(aggregateFn, [values]);
        return expectNumber(result);
      });
    });

    this.defineNative("bucketize", (seriesValue, durationValue, aggregateValue) => {
      const series = expectSeries(seriesValue);
      const duration = parseDuration(expectString(durationValue));
      const aggregateFn = expectFunction(aggregateValue);
      return series.bucketize(duration, async (values) => {
        const result = await this.callFunction(aggregateFn, [values]);
        return expectNumber(result);
      });
    });

    this.defineNative("filter", async (target, predicateValue) => {
      const predicate = expectFunction(predicateValue);
      const series = expectSeries(target);
      return series.filter(async (dp) => {
        const decision = await this.callFunction(predicate, [dp.value, dp]);
        return truthy(decision);
      });
    });

    this.defineNative("map", async (target, ...fnValues) => {
      const series = expectSeries(target);
      if (fnValues.length === 0) {
        return series;
      }
      return fnValues.reduce<Promise<DatapointSeries>>(async (accPromise, fnValue) => {
        const accSeries = await accPromise;
        const mapper = expectFunction(fnValue);
        return accSeries.map(async (dp) => {
          const mappedValue = await this.callFunction(mapper, [dp.value, dp]);
          if (mappedValue instanceof Datapoint) {
            return mappedValue;
          }
          return new Datapoint(dp.timestamp, expectNumber(mappedValue), dp.dimensions);
        });
      }, Promise.resolve(series));
    });

    this.defineNative("compose", async (...composeArgs) => {
      if (composeArgs.length < 2) {
        throw new Error("compose expects at least one stream and an aggregate function");
      }
      const aggregateFn = expectFunction(composeArgs[composeArgs.length - 1]);
      const streams = composeArgs.slice(0, -1).map((value) => expectSeries(value));
      if (streams.length === 0) {
        throw new Error("compose requires at least one stream");
      }
      return composeImpulses(streams, async (values) => {
        const result = await this.callFunction(aggregateFn, values as Value[]);
        return expectNumber(result);
      });
    });

    this.defineNative("not", value => {
        const predicate = expectFunction(value);
        return makeNativeFunction("not-predicate", async (...args) => {
            return !truthy(await this.callFunction(predicate, args));
        });
    });

    this.defineNative("and", (...predicateValues) => {
      const predicates = predicateValues.map(expectFunction);
      return makeNativeFunction("and-predicate", async (...args) => {
        for (const predicate of predicates) {
          const decision = await this.callFunction(predicate, args);
          if (!truthy(decision)) {
            return false;
          }
        }
        return true;
      });
    });

    this.defineNative("or", (...predicateValues) => {
      const predicates = predicateValues.map(expectFunction);
      return makeNativeFunction("or-predicate", async (...args) => {
        for (const predicate of predicates) {
          const decision = await this.callFunction(predicate, args);
          if (truthy(decision)) {
            return true;
          }
        }
        return false;
      });
    });

    this.defineNative("dimension-is", (keyValue, valueValue) => {
      const key = expectString(keyValue);
      const expected = expectString(valueValue);
      return makeNativeFunction("dimension-is-predicate", async (_value, dpValue) => {
        const datapoint = expectDatapoint(dpValue);
        return datapoint.dimensions[key] === expected;
      });
    });

    this.defineNative("dim-matches", (keyValue, regexValue) => {
      const key = expectString(keyValue);
      const regex = new RegExp(expectString(regexValue));
      return makeNativeFunction("dim-matches-predicate", async (_value, dpValue) => {
        const datapoint = expectDatapoint(dpValue);
        return regex.test(datapoint.dimensions[key]);
      });
    });

    this.defineNative("no-dimension", (keyValue) => {
      const key = expectString(keyValue);
      return makeNativeFunction("no-dimension-predicate", async (_value, dpValue) => {
        const datapoint = expectDatapoint(dpValue);
        return !(key in datapoint.dimensions);
      });
    });

    this.installComparators();
    this.installArithmetic();
    this.installAggregates();
  }

  private defineNative(name: string, impl: (...args: Value[]) => Promise<Value> | Value) {
    this.builtinsEnv.define(name, makeNativeFunction(name, impl));
  }

  private installArithmetic() {
    this.defineNative("+", (...args) => args.reduce((acc, value) => (acc as number) + expectNumber(value), 0));
    this.defineNative("-", (a, b) => expectNumber(a) - expectNumber(b));
    this.defineNative("*", (...args) => args.reduce((acc, value) => (acc as number) * expectNumber(value), 1));
    this.defineNative("/", (a, b) => expectNumber(a) / expectNumber(b));
    this.defineNative("exp", (a, b) => Math.pow(expectNumber(a), expectNumber(b)));
    this.defineNative("abs", (value) => Math.abs(expectNumber(value)));
    this.defineNative("sgn", (value) => Math.sign(expectNumber(value)));
  }

  private installComparators() {
    const register = (
      name: string,
      op: (left: number, right: number) => boolean
    ) => {
      this.defineNative(name, (a: Value, b?: Value) => {
        if (typeof b === "undefined") {
          const bound = expectNumber(a);
          return makeNativeFunction(`${name}-predicate`, (value: Value) => {
            return op(expectNumber(value), bound);
          });
        }
        return op(expectNumber(a), expectNumber(b));
      });
    };

    register("<", (l, r) => l < r);
    register(">", (l, r) => l > r);
    register("<=", (l, r) => l <= r);
    register(">=", (l, r) => l >= r);
    register("=", (l, r) => l === r);
  }

  private installAggregates() {
    this.defineNative("aggregate-from", (fnValue) => {
      const binary = expectFunction(fnValue);
      return makeNativeFunction("aggregate-from-result", async (valuesValue: Value) => {
        const values = expectNumberArray(valuesValue);
        if (values.length === 0) {
          return 0;
        }
        let acc = values[0];
        for (let i = 1; i < values.length; i += 1) {
          const result = await this.callFunction(binary, [acc, values[i]]);
          acc = expectNumber(result);
        }
        return acc;
      });
    });

    this.defineNative("p", (percentValue) => {
      const percent = expectNumber(percentValue);
      return makeNativeFunction("percentile", (valuesValue: Value) => {
        const values = expectNumberArray(valuesValue);
        if (values.length === 0) {
          return 0;
        }
        const sorted = [...values].sort((a, b) => a - b);
        const rank = Math.min(sorted.length - 1, Math.max(0, Math.floor((percent / 100) * (sorted.length - 1))));
        return sorted[rank];
      });
    });

    this.defineNative("count", (valuesValue) => {
      const values = expectNumberArray(valuesValue);
      return values.length;
    });

    this.defineNative("sum", (valuesValue) => {
      const values = expectNumberArray(valuesValue);
      return values.reduce((acc, value) => acc + value, 0);
    });

    this.defineNative("avg", (valuesValue) => {
      const values = expectNumberArray(valuesValue);
      if (values.length === 0) {
        return 0;
      }
      return values.reduce((acc, value) => acc + value, 0) / values.length;
    });

    this.defineNative("min", (valuesValue) => {
      const values = expectNumberArray(valuesValue);
      if (values.length === 0) {
        return 0;
      }
      return Math.min(...values);
    });

    this.defineNative("max", (valuesValue) => {
      const values = expectNumberArray(valuesValue);
      if (values.length === 0) {
        return 0;
      }
      return Math.max(...values);
    });

    this.defineNative("std", (valuesValue) => {
      const values = expectNumberArray(valuesValue);
      if (values.length <= 1) {
        return 0;
      }
      const mean = values.reduce((acc, value) => acc + value, 0) / values.length;
      const variance = values.reduce((acc, value) => acc + Math.pow(value - mean, 2), 0) / (values.length - 1);
      return Math.sqrt(variance);
    });
  }
}

function makeNativeFunction(
  name: string,
  impl: (...args: Value[]) => Promise<Value> | Value
): NativeFunctionValue {
  return { kind: "native", name, impl };
}

export async function compute(
  client: ImpulsesClient,
  library: string,
  program: string
): Promise<Map<string, DatapointSeries>> {
  const runtime = new DslRuntime((metricName) => client.fetchDatapoints(metricName));
  // todo: save env and copy the env after evaluating the library before evaluating the program
  // to not recompute the library every time
  await runtime.evaluate(library);
  const env = await runtime.evaluate(program);
  const result = new Map<string, DatapointSeries>();
  for (const [name, value] of Object.entries(env)) {
    if (value instanceof DatapointSeries) {
      result.set(name, value);
    }
  }
  return result;
}
