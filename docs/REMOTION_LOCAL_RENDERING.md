# Remotion Local Rendering

**Verified:** 2026-08-20

## Evaluation-only licence basis

T050 may use Remotion only for the current local, non-commercial Phase-1
evaluation. The official Remotion 4 licence grants free use while evaluating
whether Remotion is a fit and before commercial use begins. This repository does
not establish that Unique Group of Institutions is otherwise eligible as an
individual, an organization with at most three employees, or a nonprofit.

Stop rendering and reassess licensing before production, operational, published,
or commercial use. If the institution is a for-profit organization with more
than three employees, a Remotion Company License is required after evaluation.
No licence key, paid service, cloud renderer, telemetry-enabled licence option,
or external media transfer is authorized by T050.

Official source: <https://www.remotion.dev/license>

## Exact dependency pins

The T050 Remotion project uses one aligned stable patch version for every
Remotion package, as required by the official package documentation:

- `remotion` `4.0.514`
- `@remotion/cli` `4.0.514`
- `@remotion/bundler` `4.0.514`
- `@remotion/renderer` `4.0.514`
- `@remotion/transitions` `4.0.514`
- `react` `19.2.3`
- `react-dom` `19.2.3`
- `typescript` `5.9.3`
- `@types/react` `19.2.7`
- `@types/react-dom` `19.2.3`

All versions are exact values without `^` or `~`, and `package-lock.json`
will be committed. Remotion `4.0.514` is the stable version identified by the
current official renderer documentation; the React and TypeScript pins follow
the current official empty template.

Official sources:

- <https://www.remotion.dev/docs/renderer>
- <https://github.com/remotion-dev/template-empty/blob/main/package.json>

## Local runtime requirements

- Official minimum: Node.js 16. The target has Node.js `24.16.0` and npm
  `11.13.0`.
- Official Windows target: x64. The project target is Windows x64.
- Remotion manages a tested Chrome Headless Shell under ignored `node_modules`.
  Remotion `4.0.514` is in the documented `4.0.452+` range using Chrome
  `149.0.7790.0`. The local adapter must use this managed browser and must not
  accept a caller-supplied browser path.
- Remotion 4.0.514 supplies its local compiled FFmpeg n7.1 binary under GPLv2+. The adapter must
  use Remotion's managed renderer boundary and must not accept caller-supplied
  FFmpeg paths, commands, codecs, compositions, or arbitrary arguments.
- Browser and FFmpeg runtime downloads stay local beneath ignored dependency or
  render storage. Media inputs and outputs never leave the project-local ignored
  storage boundary.

Official sources:

- <https://www.remotion.dev/docs/>
- <https://www.remotion.dev/docs/miscellaneous/chrome-headless-shell>
- <https://www.remotion.dev/docs/miscellaneous/ffmpeg-license>

## Approved installation boundary

The product owner approved the exact tracked dependency installation and local
browser download on 2026-08-20. Installation was confined to the T050 Remotion
subproject using the tracked lock: 300 locked entries resolve only from
`registry.npmjs.org` with integrity data, every Remotion-family package is
4.0.514, and npm reported zero vulnerabilities. Remotion's pinned Chrome Headless
Shell 149.0.7790.0 and FFmpeg n7.1 remain beneath ignored local dependency storage.
Any changed pin, source, credential request, paid licence requirement, global
installation, cloud render or media upload remains unauthorized.
