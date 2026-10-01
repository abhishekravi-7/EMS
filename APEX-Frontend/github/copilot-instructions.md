## JSP-to-React Conversion Rules

When converting JSP pages or Java entity reference material into React, produce only the user-facing UI flow and behavior. Java entities are reference material for field names, not frontend source.

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
