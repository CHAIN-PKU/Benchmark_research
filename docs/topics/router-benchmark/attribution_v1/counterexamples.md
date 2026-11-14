| task | F1 | F2 | F3 | evidence |
|---|---|---|---|---|
| axios__axios-5892 | no | no | no |  |
| briannesbitt__carbon-2752 | no | no | no |  |
| briannesbitt__carbon-2813 | no | no | no |  |
| briannesbitt__carbon-2981 | no | no | no |  |
| briannesbitt__carbon-3005 | yes | no | no | F1: adds both __serialize and __unserialize (write/read halves) to AbstractTranslator |
| caddyserver__caddy-4774 | no | no | no |  |
| caddyserver__caddy-5626 | no | no | no |  |
| caddyserver__caddy-5870 | no | no | no |  |
| caddyserver__caddy-6288 | no | no | no |  |
| faker-ruby__faker-2970 | no | no | no |  |
| fluent__fluentd-3616 | no | no | no |  |
| fluent__fluentd-3631 | no | no | no |  |
| fluent__fluentd-4030 | no | no | no |  |
| fluent__fluentd-4655 | no | no | no |  |
| fmtlib__fmt-3158 | yes | no | no | F1: two sibling parse() paths in ranges.h both changed to call underlying_.parse(ctx) |
| fmtlib__fmt-3248 | no | no | no |  |
| fmtlib__fmt-3272 | no | no | no |  |
| fmtlib__fmt-3729 | no | no | no |  |
| gohugoio__hugo-12579 | no | no | no |  |
| gohugoio__hugo-12768 | no | no | no |  |
| google__gson-1093 | no | no | no |  |
| google__gson-2134 | no | no | no |  |
| google__gson-2158 | yes | no | no | F1: byte/short/int/long/float/double adapters in TypeAdapters.java plus Gson.java double/float adapters all changed |
| google__gson-2479 | yes | no | no | F1: both registerTypeAdapter and registerTypeHierarchyAdapter get the check |
| immutable-js__immutable-js-2005 | no | no | no |  |
| immutable-js__immutable-js-2006 | no | no | no |  |
| javaparser__javaparser-4538 | no | no | no |  |
| javaparser__javaparser-4561 | no | no | no |  |
| jekyll__jekyll-8761 | yes | no | no | F1: DocumentDrop and ExcerptDrop both get name |
| jekyll__jekyll-8771 | no | no | no |  |
| jordansissel__fpm-1850 | no | no | no |  |
| jqlang__jq-2598 | no | no | no |  |
| jqlang__jq-2650 | no | no | no |  |
| jqlang__jq-2658 | yes | no | no | F1: identical jv_is_valid check added in two --jsonargs branches of main.c |
| jqlang__jq-2919 | no | no | no |  |
| laravel__framework-51195 | no | no | no |  |
| laravel__framework-52451 | no | no | no |  |
| laravel__framework-52866 | no | yes | no | F2: issue is about Config attribute with null; fix in Container returns null for any nullable unresolvable param |
| micropython__micropython-12158 | yes | no | no | F1: mp_thread_create/get_id changed in many ports (cc3200, esp32, renesas-ra, ...) |
| micropython__micropython-13039 | no | no | no |  |
| mrdoob__three.js-27395 | no | no | no |  |
| php-cs-fixer__php-cs-fixer-8064 | no | no | no |  |
| php-cs-fixer__php-cs-fixer-8075 | no | no | no |  |
| phpoffice__phpspreadsheet-3903 | no | no | no |  |
| preactjs__preact-2757 | no | no | no |  |
| preactjs__preact-2927 | no | no | no |  |
| preactjs__preact-3010 | no | no | no |  |
| preactjs__preact-3454 | no | no | no |  |
| projectlombok__lombok-3312 | no | no | no |  |
| projectlombok__lombok-3350 | no | no | no |  |
| projectlombok__lombok-3479 | no | no | no |  |
| projectlombok__lombok-3571 | yes | no | no | F1: both EclipseNode and JavacNode isStatic fixed for records (plus Eclipse/Javac util) |
| projectlombok__lombok-3594 | no | no | no |  |
| projectlombok__lombok-3674 | yes | no | no | F1: both Eclipse and Javac HandleStandardException, both constructor variants casts |
| prometheus__prometheus-10720 | no | no | no |  |
| redis__redis-10095 | no | no | no |  |
| redis__redis-11631 | no | no | no |  |
| rubocop__rubocop-13362 | no | yes | no | F2: issue shows @ivar interpolation; fix covers ivar, cvar, gvar |
| rubocop__rubocop-13424 | yes | no | no | F1: each_ancestor(:send) widened to (:send, :csend) |
| rubocop__rubocop-13479 | no | no | no |  |
| rubocop__rubocop-13680 | no | no | no |  |
| rubocop__rubocop-13687 | no | no | no |  |
| sharkdp__bat-1892 | no | no | no |  |
| sharkdp__bat-2201 | no | no | no |  |
| sharkdp__bat-2260 | no | no | no |  |
| uutils__coreutils-6682 | no | no | no |  |
| valkey-io__valkey-1499 | no | no | no |  |
| valkey-io__valkey-1842 | no | no | no |  |
| vuejs__core-11739 | no | no | no |  |

Totals (of 69): F1=yes 10, F2=yes 2, F3=yes 0.
Conservative marking; F3 found no clear hidden-spec case (e.g. bat-2201, fmt-3248, jq-2919 had the requirement stated in the issue).