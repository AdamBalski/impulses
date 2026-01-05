import { AstNode, AstList, AstNumber, AstString, parse } from "./parser.js";

function formatNode(node: AstNode, indent: number): string {
  switch (node.type) {
    case "number":
      return formatNumber(node);
    case "string":
      return formatString(node);
    case "symbol":
      return node.name;
    case "list":
      return formatList(node, indent);
  }
}

function formatNumber(node: AstNumber): string {
  if (Number.isInteger(node.value)) {
    return node.value.toString();
  }
  const fixed = node.value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return fixed || "0";
}

function formatString(node: AstString): string {
  const escaped = node.value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return `"${escaped}"`;
}

function formatList(list: AstList, indent: number): string {
  if (list.items.length === 0) {
    return "()";
  }

  const head = list.items[0];
  const rest = list.items.slice(1);
  const headText = formatNode(head, indent + 1);

  // One-line if simple head and only primitives following
  if (rest.length === 0) {
    return `(${headText})`;
  }

  const shouldSingleLine = rest.every((item) => item.type !== "list");
  if (shouldSingleLine) {
    const tail = rest.map((item) => formatNode(item, indent + 1)).join(" ");
    return `(${headText} ${tail})`;
  }

  const indentSpaces = "  ".repeat(indent + 1);
  const tail = rest
    .map((item) => indentLines(formatNode(item, indent + 1), indentSpaces))
    .join("\n");
  return `(${headText}\n${tail})`;
}

export function format(program: string): string {
  const trimmed = program.trim();
  if (!trimmed) {
    return "";
  }
  const ast = parse(trimmed);
  return ast.map((node) => formatNode(node, 0)).join("\n");
}

function indentLines(value: string, indent: string): string {
  if (!value.includes("\n")) {
    return `${indent}${value}`;
  }
  return value
    .split("\n")
    .map((line) => `${indent}${line}`)
    .join("\n");
}
