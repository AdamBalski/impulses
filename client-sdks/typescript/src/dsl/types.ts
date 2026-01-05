import { Datapoint, DatapointSeries } from "../models.js";
import { AstNode, AstSymbol } from "./parser.js";

export type Value =
  | number
  | string
  | boolean
  | Datapoint
  | DatapointSeries
  | Value[]
  | FunctionValue;

export interface FunctionValue {
  kind: "native" | "lambda";
}

export interface NativeFunctionValue extends FunctionValue {
  kind: "native";
  name: string;
  impl: (...args: Value[]) => Promise<Value> | Value;
}

export interface EnvironmentRef {
  define(name: string, value: Value): void;
  assign(name: string, value: Value): void;
  lookup(name: string): Value;
  snapshot(): Record<string, Value>;
}

export interface LambdaFunctionValue extends FunctionValue {
  kind: "lambda";
  params: string[];
  body: AstNode[];
  env: EnvironmentRef;
}

export function isFunctionValue(value: Value): value is FunctionValue {
  return typeof value === "object" && value !== null && "kind" in value;
}

export function isNativeFunction(value: FunctionValue): value is NativeFunctionValue {
  return value.kind === "native";
}

export function isLambdaFunction(value: FunctionValue): value is LambdaFunctionValue {
  return value.kind === "lambda";
}

export function isSymbol(node: AstNode, name: string): node is AstSymbol {
  return node.type === "symbol" && node.name === name;
}

export function expectNumber(value: Value): number {
  if (typeof value !== "number") {
    throw new Error("Expected number");
  }
  return value;
}

export function expectString(value: Value): string {
  if (typeof value !== "string") {
    throw new Error("Expected string");
  }
  return value;
}

export function expectSeries(value: Value): DatapointSeries {
  if (value instanceof DatapointSeries) {
    return value;
  }
  throw new Error("Expected datapoint series");
}

export function isSeries(value: Value): value is DatapointSeries {
  return value instanceof DatapointSeries;
}

export function expectFunction(value: Value): FunctionValue {
  if (!isFunctionValue(value)) {
    throw new Error("Expected function value");
  }
  return value;
}

export function expectDatapoint(value: Value): Datapoint {
  if (value instanceof Datapoint) {
    return value;
  }
  if (value instanceof DatapointSeries) {
    throw new Error("Expected datapoint but received series");
  }
  throw new Error("Expected datapoint");
}

export function expectNumberArray(value: Value): number[] {
  if (!Array.isArray(value)) {
    throw new Error("Expected list of numbers");
  }
  return value.map(expectNumber);
}

export function truthy(value: Value): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    return value.length > 0;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return Boolean(value);
}
