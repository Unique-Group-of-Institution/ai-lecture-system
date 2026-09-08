# UGI Education Slide Engine

Embedded production slide generator for the AI Lecture System.

## Contract

Input is canonical Lecture JSON validated by `schemas/lecture.schema.json`.

## Runtime

Node.js 20+ and the dependencies declared in `package.json` are required.

Django must invoke `scripts/generate-deck.mjs` through a controlled subprocess adapter. The executable and script path are application-owned configuration; request data must never select an executable or working directory.
