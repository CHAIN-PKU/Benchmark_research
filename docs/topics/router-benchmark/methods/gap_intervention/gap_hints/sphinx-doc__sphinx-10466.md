## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) Catalog.__iter__ in sphinx/builders/gettext.py builds positions and uuids in parallel from metadata, so deduplicating only locations can misalign uuids. 2) Check Message.__init__ and Catalog.add to decide which layer should deduplicate, and look for other Message constructions. 3) sphinx/templates/gettext/message.pot_t line 20 iterates message.locations.
B. 1) The same (source, line) repeated several times. 2) Output order after deduplication must stay stable, and a plain set loses the original order. 3) Same file with different line numbers must be kept. 4) Same location with different uuids.
C. 1) Read the existing tests in tests/test_build_gettext.py. 2) Check the CHANGES format for a changelog entry. 3) Look for existing deduplication or order-preserving utilities in sphinx/util.
D. 1) Add the same message at the same location repeatedly and check the .pot contains it once. 2) Add a message at different files and lines and check all are kept in first-seen order. 3) Check that locations and uuids still correspond after iterating Catalog, and run the existing gettext tests.
