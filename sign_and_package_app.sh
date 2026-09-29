#!/bin/bash -eux

_root_dir="$(dirname "$(greadlink -f "$0")")"
_product="$(cat "$_root_dir/resources/product_name.txt")"
_app="out/Default/$_product.app"
_packaging="out/Default/$_product Packaging"

if [ -n "${MACOS_CERTIFICATE_NAME:-}" ]; then
  if [ -n "${PROD_MACOS_SPECIAL_ENTITLEMENTS_PROFILE_PATH:-}" ]; then
    # Chromium embeds this profile from its packaging inputs during signing.
    cp "$PROD_MACOS_SPECIAL_ENTITLEMENTS_PROFILE_PATH" "$_packaging/Helium.provisionprofile"
  fi

  CREDENTIAL_ARGS=(store-credentials notarytool-profile)
  NOTARY_ARGS=(--notary-arg=--keychain-profile=notarytool-profile)
  if [ -n "${CI:-}" ]; then
    CREDENTIAL_ARGS+=("--keychain=$HOME/Library/Keychains/build.keychain-db")
    NOTARY_ARGS+=("--notary-arg=--keychain=$HOME/Library/Keychains/build.keychain-db")
  fi

  # Idaten: App 用パスワードの代わりに App Store Connect の API キーでも認証できるようにする
  # (鍵ファイルを渡すだけで、パスワードを人が扱わずに済む)。API キーがあればそちらを優先
  if [ -n "${PROD_MACOS_NOTARIZATION_API_KEY_B64:-}" ]; then
    _api_key="$(mktemp -d)/AuthKey_${PROD_MACOS_NOTARIZATION_API_KEY_ID}.p8"
    printf '%s' "$PROD_MACOS_NOTARIZATION_API_KEY_B64" | base64 --decode > "$_api_key"
    xcrun notarytool \
      "${CREDENTIAL_ARGS[@]}" \
      --key "$_api_key" \
      --key-id "$PROD_MACOS_NOTARIZATION_API_KEY_ID" \
      --issuer "$PROD_MACOS_NOTARIZATION_API_ISSUER"
    rm -f "$_api_key"
  else
    xcrun notarytool \
      "${CREDENTIAL_ARGS[@]}" \
      --apple-id "$PROD_MACOS_NOTARIZATION_APPLE_ID" \
      --team-id "$PROD_MACOS_NOTARIZATION_TEAM_ID" \
      --password "$PROD_MACOS_NOTARIZATION_PWD"
  fi

  python3 "$_packaging/sign_chrome.py" \
    --input out/Default \
    --output out/Default/signed \
    --identity "$MACOS_CERTIFICATE_NAME" \
    --disable-packaging --notarize \
    "${NOTARY_ARGS[@]}"

  _app="out/Default/signed/stable/$_product.app"
  # Idaten: 公証・ステープルの後に Gatekeeper で確かめる(署名直後の検査は公証前なので止めてある)
  spctl -a -vv -t exec "$_app"
else
  echo "warn: MACOS_CERTIFICATE_NAME is missing; skipping notarization" >&2
  codesign --force --deep --sign - "$_app"
fi

if [ -z "${OUT_DMG_PATH:-}" ]; then
  _chromium_version=$(cat "$_root_dir/helium-chromium/chromium_version.txt")
  _helium_revision=$(cat "$_root_dir/helium-chromium/revision.txt")
  _platform_revision=$(cat "$_root_dir/revision.txt")
  OUT_DMG_PATH="$_root_dir/build/helium_${_chromium_version}-${_helium_revision}.${_platform_revision}_macos.dmg"
fi

# Package the app
chrome/installer/mac/pkg-dmg \
  --sourcefile --source "$_app" \
  --target "$OUT_DMG_PATH" \
  --volname "$_product" --format ULMO \
  --icon "$_app/Contents/Resources/app.icns" \
  --symlink /Applications:/Applications \
  --mkdir .background \
  --copy "$_root_dir/resources/dmg_background.png:/.background/dmg_background.png" \
  --copy "$_root_dir/resources/dmg_dsstore:/.DS_Store" \
  --verbosity 2

if [ -n "${MACOS_CERTIFICATE_NAME:-}" ]; then
  codesign \
    --sign "$MACOS_CERTIFICATE_NAME" \
    --identifier dev.idaten.chromium --force \
    "$OUT_DMG_PATH"
fi
