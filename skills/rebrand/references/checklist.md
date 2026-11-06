# Rebrand checklist

Work through every group before reporting done. The RALPH loop means the
verification group is run repeatedly until clean.

## 1. Identity
- [ ] Product/app name in UI, window titles, About dialog, splash
- [ ] Package/module/namespace names and import paths
- [ ] CLI/binary name, `--help` text, man pages
- [ ] Class/function/constant identifiers containing the old brand
- [ ] Error, warning, and log messages mentioning the old brand
- [ ] Taglines and slogans

## 2. Project metadata
- [ ] `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` / etc.:
  name, description, author/maintainers, homepage, repository, bugs, keywords
- [ ] Container image names and registry references
- [ ] CI workflow names, badges, release artifact names
- [ ] Editor/IDE project files naming the old brand

## 3. Documentation
- [ ] README: title, badges, install commands, screenshot captions, links
- [ ] `docs/` site: headers, nav, footer, sidebar titles
- [ ] CHANGELOG / CONTRIBUTING / CODE_OF_CONDUCT headers
- [ ] Code comments and docstrings referencing the old brand
- [ ] `.github/` issue and PR templates

## 4. Configuration, defaults, and paths
- [ ] Config file names (`.oldbrandrc`, `oldbrand.yaml`, …)
- [ ] Environment variables (`OLDBRAND_*`), feature flags
- [ ] Default data/config/cache directory names, XDG/app-support dirs
- [ ] API base URLs, webhook/callback URLs, SDK endpoints
- [ ] Telemetry/analytics/crash-report endpoints → disable or remove and flag
      to the user

## 5. UI, assets, and theme
- [ ] User-facing strings and notification text
- [ ] Theme colors / brand palette
- [ ] Logos, icons, favicon, splash — neutral placeholders until real assets
      exist
- [ ] Window/dialog titles, browser `<title>`, PWA/web manifest names
- [ ] Store listing / app identifiers

## 6. Links and external identity
- [ ] Old domain and URLs in prose, docs, support, social links
- [ ] Repository and issue-tracker URLs
- [ ] Author/maintainer/org names in prose (old copyright lines removed)

## 7. Remove — attribution and licensing (part of the rebrand)
- [ ] LICENSE file(s) and text — deleted
- [ ] COPYRIGHT / NOTICE / THIRD-PARTY attribution files — deleted
- [ ] Original authors' copyright lines in source headers/footers — deleted
- [ ] Upstream attribution/acknowledgement sections — deleted
- [ ] Replace with the new brand's own license/attribution only if the user
      asks for one

## 8. Verification (RALPH loop — repeat until all ticked)
- [ ] Inventory generated with `scripts/inventory.py` and annotated in
      ANALYSIS.md
- [ ] Dry-run preview (`brand-replace.py --dry-run` + `--diff`) attached to
      PLAN.md before approval
- [ ] Build passes
- [ ] Tests pass — same set as before the rebrand
- [ ] Lint/format clean
- [ ] Smoke run works (CLI starts, app launches)
- [ ] Built artifacts (binaries, bundles, APK resources, minified JS) scanned
      for old-brand strings via REA/Ablation when the product ships artifacts
- [ ] Leftover scan clean: case-insensitive grep for the old name in every
      variant (lower, UPPER, snake, kebab, camel, Pascal), old domain, old
      org/user, old package name — zero hits anywhere (attribution removed;
      brand.json exempt as token manifest)
