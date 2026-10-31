# Changelog

## [1.6.0](https://github.com/Aohzan/hass-tplink-easysmartswitch/compare/1.5.0...1.6.0) (2026-10-27)

### Features

* add a button to restart the switch ([b88c0e1](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/b88c0e1b0661ff7509b0f3fc19455ae4c323b5c0))
* modernize the integration for Home Assistant 2026.10 ([ba1c5a9](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/ba1c5a9279163f4e59cbd42c9d531ce5a7ed2d81))
* ship the brand images with the integration ([7c11a78](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/7c11a7899c5d4106a66a95295f15a05592716b87))

### Bug Fixes

* accept an empty password and translate the connection error ([1db8370](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/1db83702626dc03b66d069af00d112d980497f2a))
* compute the port speeds once per update ([1751f3c](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/1751f3ca51cbf1d812a07acb0c6a338b2c9dc6e4))
* **deps:** require beautifulsoup4 4.13.3 or later ([a7ff291](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/a7ff2919664f49ea4e3d704dccf501d38d6c888b))
* detect the lost session and the rejected login from the switch answers ([8ef65bb](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/8ef65bbfa3b81fe650d2d431a416591a3d95aaf4)), closes [#7](https://github.com/Aohzan/hass-tplink-easysmartswitch/issues/7)
* handle the connection errors and timeouts of the switch ([b5e290d](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/b5e290dd3b2a80e329f0368832569a479bc80e01))
* leave the session of the switch to its web interface for 5 minutes ([c46995e](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/c46995e75d7256a85b3ba5f95d9aee4bc3531a9c)), closes [#5](https://github.com/Aohzan/hass-tplink-easysmartswitch/issues/5)
* read the packet counters of the switch as unsigned 32-bit values ([3ab71d4](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/3ab71d4c26087866852b1c11f8d64f57dc1d5a48))
* read the result of the login from logonInfo only ([365c08a](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/365c08aacdbc7b54a0beee4ba00f2d659c1af9fe))
* refuse to reconfigure the entry to the address of another switch ([2f73127](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/2f731277907542857bc90980007980714afeab05))
* show the Auto and 100M Half link status of the switch ([7e8c08a](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/7e8c08a029e51740bd706a5e8307f745c081297c))

## [1.5.0](https://github.com/Aohzan/hass-tplink-easysmartswitch/compare/1.4.0...1.5.0) (2025-04-23)

### Features

* add release ([5179718](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/51797185b69d8549382bd6ce57d35e2484af797e))

### Bug Fixes

* entry setup deprecated code ([27a4f76](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/27a4f7617b6104d4e9b4c936a9f8882121176301))
* OptionsFlow deprecated code ([8a7046f](https://github.com/Aohzan/hass-tplink-easysmartswitch/commit/8a7046fd22d3438a0c9a7339f98bbab55d297d62))

## 1.4.0

* Add German translation

## 1.3.1

* Spell fix

## 1.3.0

* Fix DeviceInfo for 2023.8 release
* Add icons

## 1.2.0

* Add french translation
* Code improvements

## 1.1.0

* Replace deprecated async_get_registry method

## 1.0.0

* Initial release
