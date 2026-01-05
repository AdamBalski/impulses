type Token = {
  type: "paren" | "number" | "string" | "symbol";
  value: string;
};

export type AstNode = AstList | AstNumber | AstString | AstSymbol;
export interface AstList {
  type: "list";
  items: AstNode[];
}

export interface AstNumber {
  type: "number";
  value: number;
}

export interface AstString {
  type: "string";
  value: string;
}

export interface AstSymbol {
  type: "symbol";
  name: string;
}

export function parse(source: string): AstNode[] {
  const tokens = tokenize(source);
  const iterator = tokens[Symbol.iterator]();
  const result: AstNode[] = [];

  let next = iterator.next();
  while (!next.done) {
    result.push(readNode(next.value, iterator));
    next = iterator.next();
  }

  return result;
}

function readNode(current: Token, iterator: Iterator<Token>): AstNode {
  switch (current.type) {
    case "number":
      return { type: "number", value: Number(current.value) };
    case "string":
      return { type: "string", value: current.value };
    case "symbol":
      return { type: "symbol", name: current.value };
    case "paren":
      if (current.value === "(") {
        const items: AstNode[] = [];
        let next = iterator.next();
        while (!next.done && !(next.value.type === "paren" && next.value.value === ")")) {
          items.push(readNode(next.value, iterator));
          next = iterator.next();
        }
        if (next.done) {
          throw new Error("Unbalanced parentheses in DSL expression");
        }
        return { type: "list", items };
      }
      throw new Error("Unexpected closing parenthesis");
  }
}

function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < source.length) {
    const char = source[i];
    if (char === "(") {
      tokens.push({ type: "paren", value: "(" });
      i += 1;
      continue;
    }
    if (char === ")") {
      tokens.push({ type: "paren", value: ")" });
      i += 1;
      continue;
    }
    if (/\s/.test(char)) {
      i += 1;
      continue;
    }
    if (char === ";") {
      while (i < source.length && source[i] !== "\n") {
        i += 1;
      }
      continue;
    }
    if (char === "\"") {
      let value = "";
      i += 1;
      while (i < source.length && source[i] !== "\"") {
        if (source[i] === "\\" && i + 1 < source.length) {
          const escapeChar = source[i + 1];
          value += escapeChar;
          i += 2;
          continue;
        }
        value += source[i];
        i += 1;
      }
      if (i >= source.length || source[i] !== "\"") {
        throw new Error("Unterminated string literal in DSL expression");
      }
      i += 1; // skip closing quote
      tokens.push({ type: "string", value });
      continue;
    }
    const numberMatch = readNumber(source, i);
    if (numberMatch) {
      tokens.push({ type: "number", value: numberMatch.match });
      i = numberMatch.nextIndex;
      continue;
    }
    const symbolMatch = readSymbol(source, i);
    tokens.push({ type: "symbol", value: symbolMatch.match });
    i = symbolMatch.nextIndex;
  }
  return tokens;
}

function readNumber(source: string, index: number): { match: string; nextIndex: number } | null {
  const numberRegex = /^(?:-?\d+(?:\.\d+)?)/;
  const slice = source.slice(index);
  const match = slice.match(numberRegex);
  if (!match) {
    return null;
  }
  return { match: match[0], nextIndex: index + match[0].length };
}

function readSymbol(source: string, index: number): { match: string; nextIndex: number } {
  const symbolRegex = /^[^\s()]+/;
  const slice = source.slice(index);
  const match = slice.match(symbolRegex);
  if (!match) {
    throw new Error(`Unexpected character '${source[index]}' in DSL expression`);
  }
  return { match: match[0], nextIndex: index + match[0].length };
}
