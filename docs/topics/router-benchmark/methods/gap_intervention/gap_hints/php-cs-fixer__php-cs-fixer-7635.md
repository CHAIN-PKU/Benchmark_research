## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. Places that may also need the fix
- FullyQualifiedStrictTypesFixer.php has several shortening paths that decide separately: determineShortType, shortenClassIfPossible, registerSymbolForImport. They are used by fixFunction/replaceByShortType, fixPhpDoc, fixExtendsImplements, fixCatch and fixClassStaticAccess. Reproduce via the `::` path first, then check the others. Only determineShortType has a same-short-name/different-long-name guard, and it sits inside the namespace-prefix branch.
- shortenClassIfPossible has no equivalent conflict check. Its isset($uses) branch, global-namespace $inUses loop and namespace-prefix branch are separate; find which branch gives the wrong CreateUrl.
- determineShortType and shortenClassIfPossible do the same job with slightly different rules, so a fix in one may leave the other unfixed.
- In determineShortType the global-namespace loop compares each import's short name with the whole $typeNameLower; check it still behaves for a name with namespace segments.
- In fixPhpDoc the import_symbols call to registerSymbolForImport uses $matches[3][0] and not the current $typeName; check whether that matters.

B. Inputs and edge cases likely to be checked
- The exact issue example in the global namespace: CreateUrl::run(), App\Actions\Folder1\CreateUrl::run() (no leading backslash) and \App\Actions\Folder2\CreateUrl::run() (leading backslash). Run with leading_backslash_in_global_namespace both true and false.
- The same conflict inside `namespace Foo;`: import A\X, plus uses of \B\X and \Foo\X, including a short name that differs only in case.
- The same conflict in type hints, return types, catch, extends/implements and docblocks (@param/@return/@throws), also with import_symbols true.

C. Existing conventions and tests to check
- tests/Fixer/Import/FullyQualifiedStrictTypesFixerTest.php already has same-short-name/different-long-name cases; read them for contexts covered and copy their style.
- The import-conflict rule in registerSymbolForImport (an existing import with the same short name means no import is registered) shows the intended behavior; shortening should follow it.
- Check the fixer's getDefinition samples and doc/rules/import/fully_qualified_strict_types.rst; regenerated docs only matter if samples change.

D. Self-tests before submitting
1. The issue example as written, with leading_backslash_in_global_namespace false then true; all three calls stay distinct and unchanged.
2. A namespaced file with import A\X, a \B\X static call and a \Foo\X static call (current namespace Foo); only the legitimate shortening happens.
3. The same conflict in a type hint and a docblock with import_symbols on; then run the whole existing fixer test file for regressions.
