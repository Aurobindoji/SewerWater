Map libraries shipped with the app (rewrite stage 2, 26-Nov-2026: no longer loaded from a CDN at run time).
Taken from the npm registry; each package checked against the registry's sha512 integrity, and Leaflet's two files
against the SRI hashes Leaflet publishes. Unchanged copies - this module's own (sewer_app and water_app share no code).

  leaflet/       Leaflet 1.9.4       BSD-2-Clause (leaflet/LICENSE)
                 leaflet.js  sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=
                 leaflet.css sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=
  leaflet-draw/  Leaflet.draw 1.0.4  MIT (leaflet-draw/LICENSE)
