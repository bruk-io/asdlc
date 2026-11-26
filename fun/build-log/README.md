# Build log

A bit of fun: an interactive 3D replay of a repository's Claude Code sessions. A village on a small planet, where each building is one asdlc task (as tall as it cost), each animal is one agent run acting out its real tool calls, and the person running it wanders about cheering them on.

Everything in the scene is drawn in code: the models are put together from simple shapes, the textures are painted on canvases, and the sky and sea are shaders. There are no downloaded assets. It was first made for the [grampus](https://github.com/bruk-io/grampus) port.

## Use it on a repository

```sh
./data/collect data/data.json --repo ~/src/my-repo   # read that repository's transcripts, task files and pull requests
./build                                              # assemble dist/index.html and dist/viewer.html from src/
python3 -m http.server -d dist                       # then open http://localhost:8000/local-index.html
```

`collect` takes `--title`, `--owner` (the name over the person's head), `--transcripts` (if Claude Code's folder for the repository is somewhere unusual) and `--build-word` (a program of that repository that should count as building or testing; may be repeated). It needs `gh` signed in to read pull requests.

`./preview page` and `./preview viewer critter --set model=opus --set mode=walk` take screenshots with headless Chrome.

## What it reads, and what it keeps

`collect` reads every Claude Code transcript for the repository. For each agent run it keeps the model, the step, the task, the cost (tokens at API list prices), how that cost built up over time, and its tool calls. A tool call is stored as a time and a one-letter kind (read, write, git, build, shell, web, delegate, skill, report, wait, failed). The person's own messages are stored as times. No tool arguments, paths, commands, output or message text are kept, and `collect` refuses to write the file if it finds an unexpected field or the home folder's name in it.

`data/data.json` is not committed. Cost is notional when the work ran on a subscription.

## What fits and what does not

- **Tasks and pull requests** come from asdlc's layout: `intent/<slug>/tasks/<nn-name>/task.md` and branches named `task/<slug>/<nn-name>`.
- **Rows** come from Workflow runs: each run is a row, and runs that build tasks are numbered waves. A repository worked on without workflows gets one row for the main session and one for side agents.
- **The person** is modelled on Bruk, with his hobbies. Change `src/assets/person.js` and `src/assets/hobbies.js` to taste.

## Layout

| Path | Contents |
|---|---|
| `src/shared/kit.js` | The drawing kit: toon materials named after CSS colour variables, canvas textures, outlines, base shapes. |
| `src/shared/particles.js` | The particle effects. |
| `src/shared/palette.css` | Every colour, as CSS variables. Assets ask for colours by these names. |
| `src/textures/` | One file per family of painted textures. |
| `src/assets/` | One file per asset or family of assets: critter, person, building parts, trees, scenery, effects. |
| `src/js/` | The page's script, in numbered parts joined in order (see below). |
| `src/page.html`, `src/style.css` | The page's markup and layout. |
| `src/viewer/` | The asset viewer. |
| `data/collect` | Builds `data/data.json` from the transcripts. |
| `build`, `preview` | The build and screenshot tools. |

### The page script

The parts of `src/js/` named `NN-scene-*.js` are, joined together, the body of one function, `setupThree()`. They share its variables, so order matters and a name declared in one is visible in the later ones.

| File | What it holds |
|---|---|
| `00-core.js`, `05-colour.js` | Loading the data, shared state, colours. |
| `10-three.js` | Opens `setupThree()`: renderer, scene, camera, sizes. |
| `12-scene-planet.js` | How the flat map is wrapped onto the ball, and how the camera is carried onto it. |
| `14-scene-controls.js` | Orbit controls and their limits. |
| `16-scene-kit.js` | The drawing kit for this scene. |
| `20-scene-terrain.js` | `ground(x, z)`: the height of the land, and the land mesh. |
| `22-scene-sea.js` | The sea and its shader. |
| `24-scene-lights.js` | Sky light, fill light and the sun. |
| `26-scene-sky.js` | The sky dome shader and the planet's rim of air. |
| `30-scene-paths-and-signs.js` | Paths, signs and the cost ruler. |
| `35-scene-scenery.js` | Trees, flowers, mushrooms, lamps, fairy lights, clouds, birds. |
| `40-scene-buildings.js` | One building per task. |
| `45-scene-agents-and-bruk.js` | The agents, what they act out, and Bruk's behaviour. |
| `50-scene-day-and-night.js` | Colours and light by time of day. |
| `52-scene-camera.js` | Flights, reframing, grab-and-roll dragging, zoom. |
| `57-scene-music.js` | The generated music. |
| `58-scene-frame.js` | The frame loop. |
| `60-scene-pointer.js` | Hover and click; closes `setupThree()`. |
| `65-timeline.js`, `70-panels.js`, `75-controls-and-clock.js` | The timeline, the building list and card, the buttons and the clock. |

### How the planet works

The village is laid out on a flat map, and the replay, the walking and the shadows are all worked out there. Each point is wrapped onto a ball only when it is drawn (a patch to three.js's shared shader code in `12-scene-planet.js`), and the camera is carried onto the ball to match. Code that needs a real position on the ball uses `bendPoint`; code that needs to go from the screen back to the map uses `unbendPoint`.

### Screenshot options

The page reads a few options from the URL hash, joined with `&`: `at=0.6` starts 60% of the way through, `cam=x,y,z,tx,ty,tz` places the camera, `do=bench` starts Bruk's free time on one activity, `music` starts with music on.

## Working on one asset

An asset is an entry in `ASSETS`:

```js
ASSETS.tree = {
  title: 'Tree',
  controls: { kind: ['round', 'pine'], fruit: ['yes', 'no'] },  // buttons in the viewer; the first value is the default
  build(kit, opts) { /* return a THREE.Object3D standing on y = 0 */ },
  animate(obj, state) { /* optional; state has the control values plus `now` (ms) and `moving` */ },
};
```

Open the viewer, pick the asset, and edit its file. `./preview viewer <asset> --set name=value` takes a still at a fixed time and angle, so two versions can be compared.
