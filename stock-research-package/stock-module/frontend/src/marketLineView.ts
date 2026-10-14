import type { MarketLineSnapshot, MarketLineTag } from "./types";

export function mainlineTagsBySymbol(
  snapshot: MarketLineSnapshot | null,
): Map<string, MarketLineTag[]> {
  const tags = new Map<string, MarketLineTag[]>();
  if (snapshot?.status !== "fresh") return tags;

  for (const line of snapshot.lines) {
    if (line.label === "观察") continue;
    const symbols = line.eligible_member_symbols.length
      ? line.eligible_member_symbols
      : line.members.map((member) => member.symbol);
    for (const symbol of symbols) {
      if (!/^\d{6}$/.test(symbol)) continue;
      const symbolTags = tags.get(symbol) ?? [];
      if (symbolTags.length >= 2) continue;
      symbolTags.push({ name: line.name, label: line.label, rank: line.rank });
      tags.set(symbol, symbolTags);
    }
  }
  return tags;
}
