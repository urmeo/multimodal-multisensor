# Pipeline design

[Editable Figma board](https://www.figma.com/board/hexcUfwWED4MIu7wjxmWrU/) · [README diagram](../images/pipeline.svg) · [FigJam source](pipeline.mmd)

The SVG contains editable text and vector shapes. Import it into Figma to edit the README layout. The Mermaid file describes the same data paths for FigJam.

Read each lane from left to right: inputs, checks, analysis and outputs. Recordings and released group tables enter separately. The dashed box marks work blocked by missing clock metadata.

Scripts and notebooks implement these steps separately. Preserve the raw-data mapping gap, clock requirements and descriptive-result limits when editing the diagram.
