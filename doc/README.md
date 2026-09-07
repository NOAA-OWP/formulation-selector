```markdown
# Building RaFTS Documentation

This directory contains the Sphinx documentation configuration for the Regionalization and Formulation Testing & Selection (RaFTS) tools. The documentation is built using `uv` to manage the Python environment and dependencies.

Follow the steps below to generate the API stubs and build the HTML documentation, ensuring that unit test files are excluded from the final build.

### Prerequisites
Ensure your `uv` environment is fully synced with the necessary development dependencies (like `sphinx` and `sphinx-rtd-theme`).
```bash
cd pkg
uv sync --all-groups
cd ..

```

---

### Step 1: Clean Old Build Files

To prevent Sphinx from using cached or orphaned `.rst` files, remove the old stubs and HTML build directory.

**Run these commands from the root of the repository (`rafts/`):**

```bash
rm -rf doc/source/rafts_*.rst
rm -rf doc/build/html

```

### Step 2: Generate API Stubs (Excluding Tests)

Use `sphinx-apidoc` to generate the reStructuredText (`.rst`) files for both packages.

We use the `-f` flag to overwrite existing files, the `-e` flag to put each module on its own page, and append the path to the `tests/` directories at the very end of the commands to explicitly exclude them from the documentation.

**Run these commands from the root of the repository (`rafts/`):**

```bash
# Generate rafts_algo stubs (excluding tests)
uv run --project pkg sphinx-apidoc -f -e -o doc/source pkg/rafts_algo/rafts_algo pkg/rafts_algo/rafts_algo/tests

# Generate rafts_prep stubs (excluding tests)
uv run --project pkg sphinx-apidoc -f -e -o doc/source pkg/rafts_prep/rafts_prep pkg/rafts_prep/rafts_prep/tests

```

### Step 3: Build the HTML

Navigate into the `doc/` directory and build the static HTML site. We pass a custom `SPHINXBUILD` variable to force `make` to use the virtual environment managed by `uv`.

```bash
cd doc
make html SPHINXBUILD="uv run --project ../pkg sphinx-build"

```

### Step 4: View the Documentation

Once the build succeeds, you can open the generated HTML files directly in your web browser.

* **Mac:** `open build/html/index.html`
* **Linux:** `xdg-open build/html/index.html`
* **Windows:** `start build/html/index.html`

```

This acts as a bulletproof reference for you or any future contributors to regenerate the documentation seamlessly! Are there any other configuration files you need help cleaning up before you commit these changes?

```