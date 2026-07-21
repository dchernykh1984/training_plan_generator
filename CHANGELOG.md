# Changelog

## [0.1.1](https://github.com/dchernykh1984/training_plan_generator/compare/v0.1.0...v0.1.1) (2026-07-21)


### Bug Fixes

* reliable release builds (linux-aarch64 on ubuntu-24.04, drop Intel macOS) ([d65c369](https://github.com/dchernykh1984/training_plan_generator/commit/d65c36996d992d3d5ec6e94acafb8533e715ee0e))

## 0.1.0 (2026-07-21)


### Features

* add --login flag to filter credentials by account ([2f305fb](https://github.com/dchernykh1984/training_plan_generator/commit/2f305fbe98d2cba8f80a910b83cd0ae35fec8886))
* add CLI with upload subcommand ([ef0fab8](https://github.com/dchernykh1984/training_plan_generator/commit/ef0fab82cbf8b62126aa161efbecf29512922752))
* add credentials providers and registry ([09b8a5f](https://github.com/dchernykh1984/training_plan_generator/commit/09b8a5f2db7c28bbb27299b950ac5f7c3f68e12b))
* add duration_type to WorkoutStep ([f4d0789](https://github.com/dchernykh1984/training_plan_generator/commit/f4d0789e5a9e246433a43b033c8382e86c079239))
* add example workout JSON and README usage ([d1943d2](https://github.com/dchernykh1984/training_plan_generator/commit/d1943d26e3fc86bcc67002759d0d4dcb21d8ba99))
* add Garmin connector and connector registry ([e2ed040](https://github.com/dchernykh1984/training_plan_generator/commit/e2ed040d10c78caf41fb4ed702580cf115092576))
* add Garmin workout payload adapter ([c0aaaa6](https://github.com/dchernykh1984/training_plan_generator/commit/c0aaaa6cdb0d605db6a5d3dd52c80a8ac1339c88))
* add metadata fields to WorkoutPlan ([4471c6e](https://github.com/dchernykh1984/training_plan_generator/commit/4471c6ee1b479221e301f34066fcd2ee060876fe))
* add name field to WorkoutStep ([b610a65](https://github.com/dchernykh1984/training_plan_generator/commit/b610a659857b94bd8175ad3204c13c951a33ff7b))
* add PySide6 GUI with credentials management and plan upload ([8777258](https://github.com/dchernykh1984/training_plan_generator/commit/8777258013bb59a84a6ac99d4db891ad9a170502))
* add templates for workout, JSON credentials, and KeePass entry ([497e649](https://github.com/dchernykh1984/training_plan_generator/commit/497e6495a62e15df9a57221da82459a70faaf392))
* add Test button to check a credential without running an upload ([66e2628](https://github.com/dchernykh1984/training_plan_generator/commit/66e262879f09258c684fb4ca9a472a0c58325e99))
* add workout cache and run logger ([ed19ac5](https://github.com/dchernykh1984/training_plan_generator/commit/ed19ac599824626fc866631de63297604d8dba39))
* add workout data model and JSON parser ([5656133](https://github.com/dchernykh1984/training_plan_generator/commit/5656133480ce58a06d57c1a19e53522282e768bb))
* change default log dir to project-local logs/ and suppress Garmin login noise ([ccdb2e3](https://github.com/dchernykh1984/training_plan_generator/commit/ccdb2e38b8a9f38ac73584b2dbca808953da9550))
* enforce single-level repeat nesting ([14e0ddf](https://github.com/dchernykh1984/training_plan_generator/commit/14e0ddf65d1f1a1a617ed56b3ef2be1498b9fc9a))
* open the edit dialog on double-click in credentials and targets tables ([0f367c7](https://github.com/dchernykh1984/training_plan_generator/commit/0f367c7243cb5c7d40aaafc72758598de11d2239))
* support dict of workouts in plan file ([f981d39](https://github.com/dchernykh1984/training_plan_generator/commit/f981d394a9f26fbb62bc30953a64aedc256ad6c1))
* update example JSON and README with new input format fields ([beaec6e](https://github.com/dchernykh1984/training_plan_generator/commit/beaec6e07175e26fb8f2a8e3193d2c6fa218fe0d))
* upload every workout from a list-format plan file to a table of targets ([62cb415](https://github.com/dchernykh1984/training_plan_generator/commit/62cb415b1e02a1db221a4e270bb01cc0cc5a7dfc))
* validate target value ranges in parser ([5b380b3](https://github.com/dchernykh1984/training_plan_generator/commit/5b380b3a1673a210703b9341d1c0986fb4438298))
* warn when Garmin expanded step count exceeds limit ([3da2b78](https://github.com/dchernykh1984/training_plan_generator/commit/3da2b789b79b5aad686429afebf058c8dfaef4ad))


### Bug Fixes

* auto-scroll upload log to bottom when new lines arrive ([4e95fe3](https://github.com/dchernykh1984/training_plan_generator/commit/4e95fe383304d89cf69b8352536f7006da75bcb0))
* avoid re-reading plan file bytes for cache save in UploadWorker ([00283fd](https://github.com/dchernykh1984/training_plan_generator/commit/00283fd7d66ec8004723957de817e8e2c36f1929))
* cache the plan file once per run instead of duplicating it per workout ([74fd5af](https://github.com/dchernykh1984/training_plan_generator/commit/74fd5af2b68ac3d0ae537107c6bac497722029e5))
* call worker.wait() after waitSignal to prevent QThread use-after-free on Linux ([754eb3b](https://github.com/dchernykh1984/training_plan_generator/commit/754eb3b313eb79eab5726c052e1f814fe97124d5))
* clear UploadWorker reference after upload completes ([2615c46](https://github.com/dchernykh1984/training_plan_generator/commit/2615c465cd327fd35353b1eaf9794336ff9506dc))
* match KeePass entries by connector name in GUI to restore CLI parity ([e1c7a60](https://github.com/dchernykh1984/training_plan_generator/commit/e1c7a601ccb53fe488b2b5fdb706dbfe1d6c8b2b))
* relabel credential name field as KeePass title when KeePass source is selected ([20a44f3](https://github.com/dchernykh1984/training_plan_generator/commit/20a44f3842bafc6ccf09034098a07d6a149c427b))
* report the real problem when a plan file maps names to workouts ([4f880c8](https://github.com/dchernykh1984/training_plan_generator/commit/4f880c8920216d69fa0ee7c0cda71de18a70531b))
* scope KeePass provider cache to a single upload instead of a module global ([76232c6](https://github.com/dchernykh1984/training_plan_generator/commit/76232c6b16a2ac5bed1209d328ef53bd828741a5))
* upgrade garminconnect to 0.3.6 (CVE-2026-54447) and install Qt EGL libs in CI ([0d28e09](https://github.com/dchernykh1984/training_plan_generator/commit/0d28e0993fae65a51fcf86c2b7a6bf6a086f5eec))
* use stored credential URL for KeePass entry lookup in GUI upload ([dfa83a8](https://github.com/dchernykh1984/training_plan_generator/commit/dfa83a8479a2ee77d29259fc7748912f0b79f40f))
* validate KeePass path before prompting and stop overstating Test results ([58fb7c8](https://github.com/dchernykh1984/training_plan_generator/commit/58fb7c89590a42869826d6e779489332ea19aa74))


### Documentation

* add contributing guidelines to README ([a2018d9](https://github.com/dchernykh1984/training_plan_generator/commit/a2018d9dc3abc1ff9e9c5b614552351882f6a098))
* add setup instructions to README ([cd13e0c](https://github.com/dchernykh1984/training_plan_generator/commit/cd13e0c9337ff854f13a00e02b4bf4fb4eae8cbc))
* document dict-of-workouts plan file format in README ([1d3dc2c](https://github.com/dchernykh1984/training_plan_generator/commit/1d3dc2c60b2dab62c27e9ba966b59e91b4f28078))
* document how to launch the GUI and where its config is stored ([ef54878](https://github.com/dchernykh1984/training_plan_generator/commit/ef54878e442ecccbd69088937a63512e4482b7b2))
* document pre-commit setup and manual run command ([4ed7add](https://github.com/dchernykh1984/training_plan_generator/commit/4ed7add0cd26909356149c2a12aa80cafe6f6f3c))
* remove redundant credentials and workout inline example from README ([02b73b8](https://github.com/dchernykh1984/training_plan_generator/commit/02b73b89f9a0b2a6b403a3aafd2f6337793f2e6e))
