# T021 Local Content Tool Record

All artifacts below are confined to Git-ignored `data/content-tools`; none is committed or
redistributed. Microsoft Defender reported zero detections for every downloaded archive, wheel,
executable and traineddata file. No real source content was accessed.

## Portable OCR runtime

- Mannheim Tesseract `tesseract-ocr-w64-setup-5.4.0.20240606.exe`:
  `https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe`,
  50,175,248 bytes, SHA-256
  `c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9`.
- Mannheim publishes no independent checksum; the hash is historical corroboration only. The
  embedded publisher is Universität Mannheim, certificate fingerprint
  `2F92CB990D57719BDCCA2D72134378614A040D9B`; the certificate is expired/not currently trusted.
  The binary is not reproducibly attested to UB-Mannheim source commit
  `55c4af18dd92ac7551ca1a62357bbbc0baa8db74`.
- The NSIS payload was listed/tested and an explicit runtime allowlist extracted without executing
  the installer. No registry, PATH, shortcut, association, elevation or system-directory change
  occurred. Runtime licenses are recorded in its extracted `doc/LICENSE` and `doc/README.md`.
- Official 7-Zip 26.01 verification helpers: `7zr.exe`, 602,112 bytes, SHA-256
  `abcf64ae1cbafddb5395e4cdd3bdc7e3e0561d54a0c6380e3dd43bdbffe519a2`;
  `7z2601-extra.7z`, 1,759,805 bytes, SHA-256
  `05cda5442075a7c6ce246ca1bbb9b1f1d6f1787a9559156f9b8b2dad29a86971`;
  `7z2601-x64.exe`, 1,658,851 bytes, SHA-256
  `d64a0468f5b5b0b0fc5b2188450bcd655b70809d97b1c4535f2884635094377d`.

## Official language data

Official `tesseract-ocr/tessdata_fast` release 4.1.0 resolves to immutable commit
`a8ba5063ab8013372a20e300da0c97ee46b92b07` and uses the repository's Apache-2.0 license.

| File | Immutable raw URL | Bytes | Git blob | SHA-256 |
|---|---|---:|---|---|
| `urd.traineddata` | `https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/a8ba5063ab8013372a20e300da0c97ee46b92b07/urd.traineddata` | 1,398,718 | `715a159d4abea25294c82971be28be215b3d1c4a` | `62e8250ce2a994106e313a82e26a516a39e2cf159d0ce3c5b5008387fd0d555f` |
| `eng.traineddata` | `https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/a8ba5063ab8013372a20e300da0c97ee46b92b07/eng.traineddata` | 4,113,088 | `bbef4675053b5b468cdb477053e28b1c698ba08e` | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |
| `osd.traineddata` | `https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/a8ba5063ab8013372a20e300da0c97ee46b92b07/osd.traineddata` | 10,562,727 | `527457ca8f8fe1fda7c2f88bce3c0e4be12be9d0` | `9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff` |

## Python 3.14 Windows x64 wheels

Installed only into `.venv` from local files with `--no-index --require-hashes`; exact hashes are
locked in `requirements-content.lock`.

| Package/wheel | Bytes | PyPI SHA-256 | License |
|---|---:|---|---|
| `pypdf-6.14.2-py3-none-any.whl` | 349,514 | `3f07891af76dc002657e04993ab9b4de81de29f9013b9761d0b7968bff12e946` | BSD-3-Clause |
| `pypdfium2-5.12.1-py3-none-win_amd64.whl` | 3,859,845 | `9609be73a6701a68f29dffe0335f7a2e4b3ba581542ed65d35d49f761a4600ca` | BSD-3-Clause/Apache-2.0 and bundled dependency licenses |
| `pillow-12.3.0-cp314-cp314-win_amd64.whl` | 7,237,707 | `fdafc9cce40277e0f7a0feabce0ee50dd2fa1800f3b38015e51296b5e814048d` | MIT-CMU |

## Synthetic execution result

The explicit local Tesseract executable reported version `5.4.0.20240606` and listed only the
approved `eng`, `osd` and `urd` models. Fresh synthetic PNG, JPG and PDF-rendered pages produced
logical Unicode `اردو زبان` and `Synthetic English lesson`; Urdu code points were preserved and
were neither reversed nor transliterated. TSV retained word confidence and bounding positions.
An intentionally rotated synthetic English page was orientation-corrected. No Tesseract process
retained a network connection, and all inputs/outputs remained in ignored local storage.

OCR does not reliably understand equations, diagrams or complex/multi-column layouts. These pages,
and any low-confidence result, require teacher review against the immutable original page and its
stored provenance.
## Dependency lock assessment

requirements-content.lock is intentionally a T021 extraction-runtime lock, not a claim that the
entire application environment is transitively locked across operating systems. It pins the exact
three content-processing distributions and the verified Python 3.14 Windows x64 wheel hashes used
for Pillow, pypdf and pypdfium2. Tesseract and its language data are separately versioned and
hashed above. Django and packaging/build transitive dependencies remain declared by compatible
ranges in pyproject.toml; a full cross-platform hash lock is deferred until the project selects
one deployment target and lock-generation workflow. Phase 1 mitigates that deferral with the
existing isolated virtual environment, offline require-hashes installation for T021 wheels,
pip check, clean-migration tests and CI installation/testing. No dependency was installed or
downloaded during the T021 review corrections.
