# Contributing to EcoLoco

Thanks for helping. Every pull request is read by a maintainer before it's merged.

## Ways to help

- **A plant shows the wrong status.** Open a [wrong plant status](https://github.com/Aydin-codes/EcoLoco-FL/issues/new?template=wrong-status.yml) issue with a link to a source that says otherwise. This is the most useful report we get.
- **Something is broken.** Open a [bug report](https://github.com/Aydin-codes/EcoLoco-FL/issues/new?template=bug.yml).
- **An idea.** Open an [idea](https://github.com/Aydin-codes/EcoLoco-FL/issues/new?template=idea.yml) issue before writing code, so we can agree on it first.
- **Code.** Look for issues labelled [good first issue](https://github.com/Aydin-codes/EcoLoco-FL/issues?q=is%3Aopen+label%3A%22good+first+issue%22) or [help wanted](https://github.com/Aydin-codes/EcoLoco-FL/issues?q=is%3Aopen+label%3A%22help+wanted%22).

## Plant data

Plant facts are the part of EcoLoco people trust most, so they have stricter rules than code:

- Every fact needs a link to where it came from. No fact is written by AI.
- A plant can only be recommended after it passes the check in [docs/plant-checklist.md](docs/plant-checklist.md): native per the USF Atlas, found in the county, every fact matched to its source, and the "replaces" pairing makes sense. Who checked it and when goes in [docs/plant-checklist-verified.csv](docs/plant-checklist-verified.csv).
- Lists that come from an outside source (the FISC invasive list, USDA names, ZIP codes) are rebuilt with the scripts in `backend/scripts/`, not edited by hand.

## Setting up

Follow [Run it yourself](README.md#run-it-yourself) in the README. You need your own free Pl@ntNet key and an OpenAI key to run the app, but not to run the tests.

## Before you open a pull request

1. Run both test suites: `python -m pytest` from `backend/` and `npm test` from the top folder. GitHub runs them too, and a pull request can't be merged until they pass.
2. If you add, rename or remove a screen, an API call, a backend route, a service function or a data file, update the map in `docs/architecture.html` and run `node docs/sync-architecture.mjs`. It must pass.
3. If your change affects what the app takes in or shows, update the README in the same pull request.
4. Never commit a `.env` file or any API key.
5. Keep each pull request to one change, and explain what you tested.

## License

By contributing, you agree your work is released under the [MIT license](LICENSE).
