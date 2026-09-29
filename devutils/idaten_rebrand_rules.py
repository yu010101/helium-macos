# Copyright 2026 Radineer
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""Rules for devutils/idaten_name_substitution.py (exclusions and rewrites).

Policy (decided 2026-09-29):
 1. Every product name shown on screen becomes "Idaten".
 2. Not replaced: (a) license / copyright notices (GPL-3.0; "based on Helium"
    and "The Helium Authors" stay in About / credits), (b) mechanism names:
    the helium:// scheme, internal IDs (IDS_HELIUM_*, prefs, switches,
    extension IDs), URLs (helium.computer, github.com/imputnet/...).
    (b) needs no list: the word rule is case-sensitive and ASCII-bounded, so
    "helium://", "helium.computer", "kHeliumFoo", "IDS_HELIUM_X" never match.
 3. "Helium services" (servers operated by imput) are not simply renamed:
    the provider is stated. Titles use the long form, running text the short
    form. The imput partner program is treated the same way in text, but its
    onboarding badge is not shown at all (see the PARTNER rules below).
"""

OLD = 'Helium'
NEW = 'Idaten'

SVC_LONG_EN = 'Idaten connected services (provided by imput / Helium)'
SVC_SHORT_EN = 'Idaten connected services'
SVC_LONG_JA = 'Idaten の接続サービス(提供: imput / Helium)'
SVC_SHORT_JA = 'Idaten の接続サービス'

# --- 2(a): kept as "Helium" (text and translations untouched) -------------
# Matched by message name; every other message with the same fingerprint
# (same English text, e.g. the iOS copy) is kept as well.
EXCLUDED_MESSAGES = {
    'IDS_ABOUT_VERSION_COMPANY_NAME',      # "The Helium Authors"
    'IDS_ABOUT_VERSION_COPYRIGHT',         # "Copyright {year} The Helium Authors. All rights reserved."
    'IDS_IOS_ABOUT_VERSION_COMPANY_NAME',
    'IDS_IOS_ABOUT_VERSION_COPYRIGHT',
}

# --- 1 + 2(a) + 3: explicit rewrites --------------------------------------
# name -> {lang: [(regex, replacement), ...]}; 'en' is the .grd source text.
# Each regex must match at least once, else the stage fails (drift guard).
# Languages without an entry get the generic word rule on their existing
# translation, which is moved to the new fingerprint (no translation lost).
# 'en-GB' reuses the 'en' rules.
# Names that share one fingerprint (same English text) must have identical
# rules; the stage checks this.
_SVC_TITLE = {
    'en': [(r'Helium services', SVC_LONG_EN)],
    'ja': [(r'Helium サービス', SVC_LONG_JA)],
}
_SVC_CONNECT_TOGGLE = {
    'en': [(r'Allow connecting to Helium services', 'Allow ' + SVC_SHORT_EN)],
    'ja': [(r'Helium サービスへの接続を許可する', SVC_SHORT_JA + 'の利用を許可する')],
}
_SVC_ALLOW = {
    'en': [(r'Helium services', SVC_SHORT_EN)],
    'ja': [(r'Helium サービス', SVC_SHORT_JA)],
}
_SVC_OWN_INSTANCE = {
    'en': [(r'your own instance of Helium services', 'your own instance of the connected services (Helium services)')],
    'ja': [(r'独自の Helium サービスインスタンス', '独自の接続サービス(Helium services)インスタンス')],
}

REWRITES = {
    # --- About / version page: keep "based on Helium" (policy 2a) ---
    'IDS_VERSION_UI_LICENSE': {
        'en': [(r'Helium is made possible by the ', 'Idaten is based on Helium and made possible by the ')],
        'ja': [(r'Helium は ?', 'Idaten は Helium をもとにしており、')],
    },

    # --- Services: onboarding page (helium://setup) ---
    'IDS_HELIUM_ONBOARDING_SERVICES_TITLE': _SVC_TITLE,
    'IDS_HELIUM_ONBOARDING_SERVICES_CONNECTION_TITLE': _SVC_CONNECT_TOGGLE,
    'IDS_HELIUM_ONBOARDING_SERVICES_CONNECTION_DESC': {
        'en': [(r'Helium services provide ', SVC_SHORT_EN + ', operated by imput (the developer of Helium), provide '),
               (r'but Helium will not make', 'but Idaten will not make')],
        'ja': [(r'Helium サービスは、', SVC_SHORT_JA + '(imput 社〔Helium の開発元〕が運営)は、'),
               (r'Helium はウェブリクエスト', 'Idaten はウェブリクエスト')],
    },
    'IDS_HELIUM_ONBOARDING_WELCOME_FOOTER': {
        'en': [(r'Helium services', SVC_SHORT_EN + ' (provided by imput / Helium)')],
        # no ja translation upstream yet (Helium i18n batch pending)
    },
    'IDS_HELIUM_ONBOARDING_SERVICES_INSTANCE_TITLE': _SVC_OWN_INSTANCE,
    'IDS_HELIUM_ONBOARDING_SERVICES_INSTANCE_DESC': {
        'en': [(r'your own instance of Helium services', 'your own instance of the connected services (Helium services)'),
               (r'in Helium settings', 'in Idaten settings')],
        'ja': [(r'Helium サービスの独自インスタンス', '接続サービス(Helium services)の独自インスタンス'),
               (r'Helium の設定', 'Idaten の設定')],
    },
    # Partner badge: NOT shown (decided 2026-09-29). The component that
    # renders it is emptied by patches/idaten/core/
    # idaten-remove-onboarding-partner.patch. The two messages still exist in
    # helium_onboarding_strings.grdp (and in the pak via loadTimeData), so
    # they stay classified here: dropping these rules would trip PHRASE_GUARD
    # ("Helium Partner") and fail the stage. The text is never rendered.
    'IDS_HELIUM_ONBOARDING_PARTNER_TITLE': {
        'en': [(r'Helium Partner', 'imput / Helium partner')],
        'ja': [(r'Helium パートナー', 'imput / Helium のパートナー')],
    },
    'IDS_HELIUM_ONBOARDING_PARTNER_TOOLTIP': {
        'en': [(r'support the development of Helium\.',
                'support the development of Helium by imput, which Idaten is based on.')],
        'ja': [(r'Helium の開発を支援します。', 'Idaten のもとになっている Helium(imput 社)の開発を支援します。')],
    },

    # --- Services: settings (helium://settings/privacy/services etc.) ---
    'IDS_SETTINGS_HELIUM_SERVICES': _SVC_TITLE,
    'IDS_SETTINGS_HELIUM_SERVICES_DESCRIPTION': {
        'en': [(r'Manage what Helium services are allowed',
                'Manage which ' + SVC_SHORT_EN + ' (provided by imput / Helium) are allowed')],
        'ja': [(r'Helium サービス', SVC_LONG_JA)],
    },
    'IDS_SETTINGS_HELIUM_SERVICES_TOGGLE': _SVC_CONNECT_TOGGLE,
    'IDS_SETTINGS_HELIUM_SERVICES_OVERRIDE': _SVC_OWN_INSTANCE,
    'IDS_SETTINGS_HELIUM_SERVICES_OVERRIDE_DESCRIPTION': _SVC_OWN_INSTANCE,
    'IDS_SETTINGS_HELIUM_SERVICES_OVERRIDE_ARIA_LABEL': {
        'en': [(r'Helium services', 'the connected services (Helium services)')],
        'ja': [(r'Helium サービス', '接続サービス(Helium services)')],
    },
    'IDS_SETTINGS_HELIUM_SCHEMA_NOTICE_TITLE': {
        'en': [(r'Helium services', SVC_LONG_EN)],
        'ja': [(r'Helium サービス', SVC_LONG_JA)],
    },
    'IDS_SETTINGS_HELIUM_SERVICES_SETUP_PENDING_TEXT': _SVC_ALLOW,
    'IDS_SETTINGS_LANGUAGES_DICTIONARY_DOWNLOAD_FAILED_HELP_HELIUM': {
        'en': [(r'Helium services', SVC_SHORT_EN),
               (r'from Helium servers', 'from the imput (Helium) servers')],
        'ja': [(r'Helium サービス', SVC_SHORT_JA),
               (r'Helium サーバー', 'imput 社(Helium)のサーバー')],
    },
    # --- Services: app menu / download bubble / components page ---
    'IDS_APPMENU_TOOLTIP_HELIUM_SERVICES_UPDATE': _SVC_ALLOW,
    'IDS_HELIUM_SERVICES_SCHEMA_MENU_ITEM': _SVC_ALLOW,
    'IDS_DOWNLOAD_BUBBLE_INTERRUPTED_SUBPAGE_SUMMARY_HELIUM_SERVICES_DISABLED': _SVC_ALLOW,
    'IDS_COMPONENTS_SVC_STATUS_ERROR_HELIUM_SERVICES': _SVC_ALLOW,
}

# After rewrites, no other message may still contain these phrases: a new
# upstream string mentioning the services must be classified by a human.
PHRASE_GUARD = ['Helium services', 'Helium Partner', 'Helium servers']

# --- code / web files with user-visible literals ---------------------------
# (path, kind, minimum hits). kind: c = C/C++ "..." literals, js = JS string
# literals, html = <title> only. Phrase rules run before the word rule.
CODE_FILES = [
    ('chrome/browser/helium_flag_entries.h', 'c', 15),        # helium://flags names/descriptions
    ('components/helium_services/schema.cc', 'c', 1),         # services changelog dialog
    ('components/extstore_fixups/chrome-webstore.js', 'js', 1),  # "Add to Helium" on the Web Store
    ('components/helium_onboarding/index.html', 'html', 1),   # <title>Helium Setup</title> (before JS sets it)
]
CODE_PHRASES = [
    ('Helium services', SVC_LONG_EN),
]
