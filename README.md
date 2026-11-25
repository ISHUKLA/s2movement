# s2movement

s2movement is a local tool in development for actuaries reviewing two consecutive annual Solvency II submissions from a solo European life insurer using the Standard Formula. It will reconcile movements in technical provisions, eligible own funds, SCR and the solvency ratio in an Excel workbook, with figures traceable to reported cells. Step 0.0 provides the Python package and development tools.

From the repository root, use `uv` (verified with 0.13.8) and `make` in a POSIX shell.

```sh
make setup
make check
```

**Put real reporting packages in `private/`. They contain confidential pre-submission figures and must never be committed.**
