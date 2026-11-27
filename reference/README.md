# Official reference files

Step 2 places the official EIOPA files here. For each file, record its filename, source URL, version and SHA-256 digest in `manifest.csv`. Commit this README and the manifest only.

For future XBRL ingestion, `make fetch-taxonomy` explicitly downloads the
official 2.8.2 package with external files and checks its manifest digest. The ZIP
remains ignored by Git. A comparison run must not download taxonomy files.
