## JSP-to-React / Angular UI Conversion & Enrichment Rules

When converting JSP pages or Java entity reference material into React or Angular, produce full-fidelity, enterprise-grade, modern UI components. Java entities are reference material for field names, not frontend source.

### UI Enrichment & Full-Fidelity Mandates
1. **Preserve 100% JSP Structure & Behavior**: Preserve all forms, input fields, types, names, validation rules, buttons, links, tables, `<c:forEach>` loops, `<c:if>` conditionals, navigation headers, footers, alerts, and modals.
2. **Elevate Presentation to Enterprise Grade**:
   - **Container & Layout**: Wrap pages in modern card/container layouts (`modern-container`, `modern-card`, `card shadow-sm`, or MUI `Card`/`Container`).
   - **Form Controls**: Wrap every input field in accessible form groups with styled labels (`form-label`), inputs (`form-control`), and focus states.
   - **Buttons & Hierarchy**: Replace plain buttons with distinct primary (`btn btn-primary shadow-sm`) and secondary (`btn btn-outline-secondary`) action buttons, including FontAwesome / Lucide icons.
   - **Tables & Data**: Wrap legacy `<table>` tags in responsive wrappers (`modern-table-wrapper`, `table-responsive`) with styled headers, hover rows (`table-hover`), and dynamic state mapping.
   - **Status Badges & Alerts**: Convert status strings (Active, Inactive, Pending) into visual pill badges (`badge badge-success`, `badge-warning`), and messages into alert callouts (`alert alert-info`).
3. **Dynamic State & Reactive Data**:
   - Use reactive state hooks (`useState`, `useEffect`) in React or `@Component` signals/RxJS in Angular.
   - Map lists dynamically: `{items.map((item, idx) => ( ... ))}`. Never emit hardcoded static rows.

### Output Language Gate

Before emitting any `.ts` or `.tsx` file, verify that the file contains only TypeScript or JSX syntax: imports, functions, constants, components, JSX, interfaces, and type declarations. Never include Java syntax such as `package`, `import jakarta.*`, `@Entity`, `@Table`, `public class`, getters, or setters. If Java syntax is detected, emit exactly:

`LANGUAGE FAULT — <filename> contained Java, not TypeScript. Reference material (entity classes, backend source) is for extracting field names only and must never appear as file content. Regenerating.`

Then regenerate that file as TypeScript/JSX only. Use entity fields only as frontend data shape information, for example:

- `User`: `username`, `password`, `passwordConfirm`, `roles`
- `Document`: `title`, `link`, `description`, `userId`, `id`

Do not copy entity declarations, persistence annotations, Java imports, or backend implementation into React files.

### Repetition Gate

While composing each file, compare every new line with the previous two lines already emitted in that same file. If a line is identical to either previous line, stop that repeated section immediately and continue with the next distinct section. If any duplicate line is suppressed, prepend:

`REPETITION GATE TRIGGERED — <n> duplicate lines suppressed`

The generated file must still finish completely with balanced braces, brackets, parentheses, JSX tags, and a real export statement. Never stop mid-token, attribute, JSX element, or function.

### Pre-Output Gate

Run this check silently immediately before presenting every generated file:

1. Search `.ts` and `.tsx` output for Java markers: `package`, `import jakarta.`, `@Entity`, `@Table`, `public class`, getters, and setters. On a match, apply the Output Language Gate and regenerate.
2. Search for three or more consecutive identical lines. On a match, apply the Repetition Gate and regenerate the affected section.
3. Confirm brackets and JSX tags are balanced and the file ends with a complete export, such as `export default Component;` or a valid named export.

Only present files after all three checks pass. If a requested JSP source is missing or blocked, create a React placeholder with a clear TODO and preserve the same gates.
