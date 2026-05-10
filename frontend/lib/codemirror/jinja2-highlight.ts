import {
  Decoration,
  DecorationSet,
  EditorView,
  MatchDecorator,
  ViewPlugin,
  ViewUpdate,
} from "@codemirror/view";

const variableDeco = Decoration.mark({ class: "cm-jinja2-variable" });
const blockDeco = Decoration.mark({ class: "cm-jinja2-block" });

const variableMatcher = new MatchDecorator({
  regexp: /\{\{[\s\S]*?\}\}/g,
  decoration: () => variableDeco,
});

const blockMatcher = new MatchDecorator({
  regexp: /\{%[\s\S]*?%\}/g,
  decoration: () => blockDeco,
});

function createHighlightPlugin(matcher: MatchDecorator) {
  return ViewPlugin.fromClass(
    class {
      decorations: DecorationSet;
      constructor(view: EditorView) {
        this.decorations = matcher.createDeco(view);
      }
      update(update: ViewUpdate) {
        this.decorations = matcher.updateDeco(update, this.decorations);
      }
    },
    { decorations: (v) => v.decorations }
  );
}

export const jinja2Highlight = [
  createHighlightPlugin(variableMatcher),
  createHighlightPlugin(blockMatcher),
];
