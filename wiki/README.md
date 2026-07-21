# radreport wiki (source)

This folder holds the source of the [radreport GitHub wiki][wiki]. GitHub stores
a project's wiki in a separate git repository (`radreport.wiki.git`); keeping the
pages here in the main repo lets them be reviewed alongside code and published to
the wiki.

## Publishing to the GitHub wiki

The GitHub wiki must be initialized once (create any page via the repo's **Wiki**
tab). Then, from the repo root:

```bash
git clone https://github.com/mustafamm072/radreport.wiki.git /tmp/radreport.wiki
cp wiki/*.md /tmp/radreport.wiki/
cd /tmp/radreport.wiki
git add -A && git commit -m "Sync wiki from main repo" && git push
```

## Pages

| Page | Contents |
|------|----------|
| [Home](Home.md) | Overview and navigation |
| [Getting Started](Getting-Started.md) | Install and first parse |
| [CLI Reference](CLI-Reference.md) | Every flag, with examples |
| [Parsing](Parsing.md) | Sections, measurements, findings |
| [Critical Findings](Critical-Findings.md) | Alerting and negation |
| [Follow-up Recommendations](Follow-up-Recommendations.md) | Interval/modality/urgency |
| [Interval Change](Interval-Change.md) | Prior-study comparison |
| [Report Templates](Report-Templates.md) | Completeness checking |
| [De-identification](De-identification.md) | PHI redaction |
| [FHIR Export](FHIR-Export.md) | DiagnosticReport output |
| [API Reference](API-Reference.md) | Public classes and functions |
| [FAQ](FAQ.md) | Common questions |
| [Known Issues](Known-Issues.md) | Limitations |
| [Contributing](Contributing.md) | Dev setup and conventions |

Special pages `_Sidebar.md` and `_Footer.md` render on every wiki page.

[wiki]: https://github.com/mustafamm072/radreport/wiki
