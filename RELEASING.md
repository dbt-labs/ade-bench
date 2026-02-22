# Releasing ade-bench

## Version scheme

We follow [PEP 440](https://peps.python.org/pep-0440/) versioning:

- **Release candidates:** `1.0.0rc1`, `1.0.0rc2`, ...
- **Stable releases:** `1.0.0`

## How to release

1. **Bump the version** in `pyproject.toml` via a PR to `main`.
2. **Merge** the PR.
3. **Trigger the publish workflow** from the GitHub Actions UI:
   Actions > "Publish to PyPI" > Run workflow (from `main`).

That's it. The workflow builds, tests, and publishes to PyPI.

## Installing

```bash
# Stable release
uv add ade-bench

# Release candidate (pre-release)
uv add --prerelease allow ade-bench
```
