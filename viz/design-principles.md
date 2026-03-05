# Visualization Design Principles
## Cavela Tariff Tracker — Visual Layer

*Grounded in Tufte, Bostock, Ortiz, Bremer, Wickham, and Wilkinson's Grammar of Graphics.*

---

## Practitioner Philosophies

### Edward Tufte
**Philosophy:** Maximize the data-ink ratio. Every pixel should convey information; remove everything that doesn't. "Above all else, show the data." Chartjunk—decorative elements, redundant encodings, gratuitous dimensionality—actively harms comprehension.
**Techniques:** Sparklines, small multiples, micro/macro readings, layered information density.
**On mapping data to marks:** Every mark must earn its place. If a mark doesn't encode data, delete it. Gridlines, borders, and legends are often confessions that the visualization failed to be self-evident.

### Mike Bostock (D3.js / Observable)
**Philosophy:** Visualization is data transformation, not template selection. Bind data to DOM elements, then let joins, scales, and selections express the mapping declaratively. The grammar is: select, bind, enter, update, exit.
**Techniques:** Data joins, general update pattern, force layouts, geographic projections—all built from the same primitive: binding data to marks.
**On mapping data to marks:** "D3 is not a charting library." You don't pick a chart type; you map data fields to visual properties (position, size, color, shape) through scales. The mark *is* the data.

### Santiago Ortiz
**Philosophy:** Visualization is exploration, not presentation. Interactivity reveals structure that static views hide. Complex data deserves complex, navigable representations—networks, trees, recursive structures.
**Techniques:** Highly interactive network graphs, zoomable treemaps, recursive/fractal layouts, text-as-data visualizations.
**On mapping data to marks:** Marks should be entry points into deeper structure. A node isn't just a dot—it's a portal. The mapping should invite traversal, not just reading.

### Nadieh Bremer
**Philosophy:** Data art and data accuracy are not in tension. Unconventional, beautiful forms (radial layouts, hand-crafted shapes, organic curves) can encode data precisely if the mapping is rigorous. Emotion and information coexist.
**Techniques:** Bespoke SVG shapes, radial/spiral layouts, layered transparency, annotation as narrative, custom color palettes with semantic meaning.
**On mapping data to marks:** Go beyond rectangles and circles. The shape of the mark can itself carry meaning—but only if the encoding is honest. Beauty without accuracy is decoration; accuracy without beauty is a spreadsheet.

### Hadley Wickham
**Philosophy:** Visualization should follow a grammar: map variables to aesthetics, choose geometric objects (geoms), apply statistical transformations, then facet. This separates *what* you show from *how* you show it, making the design space composable.
**Techniques:** ggplot2's layered grammar (data + aesthetic mapping + geom + stat + facet + coord + theme), tidy data as prerequisite, pipelines of transformation.
**On mapping data to marks:** The aesthetic mapping *is* the visualization. `aes(x=year, y=value, color=category)` is a complete specification. The geom (mark type) is a separate, interchangeable decision.

### Leland Wilkinson (Grammar of Graphics)
**Core framework:** Visualization is a pipeline: DATA → TRANS (transform) → SCALE → COORD → ELEMENT (marks) → GUIDE (axes/legends). Each stage is independent and composable. There are no "chart types"—only combinations of these algebraic components. This separates the statistical question from the visual answer.

---

## Consolidated Design Principles

**1. Marks, not chart types.**
There are no bar charts, line charts, or scatter plots. There are rectangles, lines, and circles positioned by scales. Compose marks to answer questions; don't select templates.

**2. The aesthetic mapping is the design.**
Explicitly bind each data field to a visual channel (position x, position y, color, opacity, size, text). This mapping is the single source of truth for what the visualization communicates. Everything else is rendering.

**3. Data flows in, marks flow out.**
Separate the pipeline: raw data → transform/aggregate → scale → encode → render. Each stage is a pure function. Data never lives inside the visualization layer; it passes through it.

**4. Maximize data-ink; earn every mark.**
If a visual element doesn't encode a data value or orient the reader, remove it. Gridlines, borders, background fills, and legends are costs—justify each one. Prefer direct labeling over legends. Prefer whitespace over dividers.

**5. One color scale, varied by saturation and opacity.**
A single hue family (with transparency and saturation variation) creates hierarchy without visual noise. Reserve color contrast for the one distinction that matters most. Multiplying hues multiplies cognitive load.

**6. Typography is a first-class encoding channel.**
Use a typographic scale (e.g., 11 / 13 / 16 / 20 / 25px) to encode hierarchy: title → annotation → axis label → tick label. White space between groups encodes structure. Type carries more information than most decorative marks.

**7. Small multiples over overloaded views.**
When data has a categorical dimension, facet into repeated, aligned panels rather than layering series on one plot. Comparison across aligned, minimal panels is faster and more accurate than decoding a legend.

**8. Scales are the bridge; make them explicit.**
Every `d3.scaleLinear()`, `d3.scaleLog()`, `d3.scaleBand()` is a design decision about how data maps to perception. Choose scales that preserve the structure you want the reader to see. Log for magnitudes, linear for differences, ordinal for categories.

**9. Compose answers, not displays.**
A visualization should answer a specific question ("Which regions grew fastest?"), not just display a dataset. The question determines the mark type, the sort order, the filtering, and the annotation. If you can't state the question, you're not ready to encode.

**10. Functional composition over imperative mutation.**
Write D3 code as pipelines of pure transformations: `data.filter().map().sort()` → `scale()` → `bindings`. Avoid stateful object graphs. Each function takes data in and returns marks out. This makes the visualization testable, debuggable, and recomposable.

**11. Annotation is not optional.**
The gap between a data display and a data argument is annotation. Title the finding, not the axes. Label the outlier, not just the trend. Callouts, reference lines, and contextual text transform marks into meaning.

**12. Progressive disclosure through interaction.**
Show the summary first; reveal detail on demand. Hover for values, click for context, zoom for resolution. The initial view should be legible in two seconds; the interactive depth should reward minutes of exploration.
