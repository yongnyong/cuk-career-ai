import type ELK from "elkjs/lib/elk.bundled.js";
import type { TreeNode } from "./engine";
import { layoutProgression } from "./treeProgression";

export type TreeLayout = ReturnType<typeof layoutProgression>;
let elk: Promise<InstanceType<typeof ELK>> | undefined;

// Only graph structure affects placement. Completion and recommendation do not.
export function layoutKey(tree: TreeNode[]) {
  return JSON.stringify(tree.map(n => [n.skill, n.depth, [...n.prereq].sort(), [...n.sequence ?? []].sort()])
    .sort((a, b) => String(a[0]).localeCompare(String(b[0]))));
}

export async function layoutTree(tree: TreeNode[]): Promise<TreeLayout> {
  const layout = layoutProgression(tree);
  if (!tree.length) return layout;
  const ids = new Set(tree.map(n => n.skill));
  const instance = await (elk ??= import("elkjs/lib/elk.bundled.js").then(({ default: Constructor }) => new Constructor()));
  const graph = await instance.layout({
    id: "tree", layoutOptions: {
      "elk.algorithm": "layered", "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "46", "elk.layered.spacing.nodeNodeBetweenLayers": "110",
      "elk.randomSeed": "1", "elk.separateConnectedComponents": "false",
    },
    children: [...tree].sort((a, b) => a.skill.localeCompare(b.skill))
      .map(n => ({ id: n.skill, width: 180, height: 150 })),
    edges: tree.flatMap(n => [...new Set([...n.prereq, ...n.sequence ?? []])].filter(p => ids.has(p))
      .map(p => ({ id: `${p}:${n.skill}`, sources: [p], targets: [n.skill] })))
      .sort((a, b) => a.id.localeCompare(b.id)),
  });
  const positions = new Map(graph.children?.map(n => [n.id, n.x ?? 0]));
  // ELK chooses horizontal order; explicit learning stages determine vertical bands.
  // Repack each band to prevent disconnected components overlapping after stage alignment.
  for (const band of layout.bands) {
    band.skills.sort((a, b) => (positions.get(a) ?? 0) - (positions.get(b) ?? 0) || a.localeCompare(b));
    band.skills.forEach((id, index) => layout.positions.set(id, { x: index * 226, y: band.y + 90 }));
  }
  return layout;
}
