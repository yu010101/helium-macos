#!/bin/bash -eux

# Unpacking script for GitHub Actions

echo "Checking sha256sum of archive:"
sha256sum -c sums.txt

_src_dir="$PWD/build/src"
ls -lrt

mkdir build
echo "Extracting build archive"
tar -C build -xf build_src.tar.zst

rm build_src.tar.zst

# Idaten: 前の段のコンパイル結果のキャッシュを戻す(github_prepare_artifacts.sh を参照)
if [ -f sccache.tar.zst ]; then
  mkdir -p "$(dirname "$SCCACHE_DIR")"
  tar -C "$(dirname "$SCCACHE_DIR")" -xf sccache.tar.zst
  rm sccache.tar.zst
  du -hs "$SCCACHE_DIR"
else
  echo "warn: no sccache archive from the previous phase"
fi

sudo df -h
sudo du -hs "$_src_dir"
