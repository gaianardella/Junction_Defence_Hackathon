"""Standalone viewer for localizations.json.

Renders the TDOA pipeline output on a real lat/lon map (OpenStreetMap
tiles, no API key required). Pick a scenario from the dropdown; the
map centres on the drone footprint and shows:

  · drone positions (coloured circles)
  · estimated source (red star + cross)
  · 95% confidence cloud (translucent polygon)

Right rail summarises CEP50 / GDOP / bearing / distance and the
per-drone σ_t / σ_pos values that were fed into the MC.

Run
---
    python -m triangulation.viewer detection/output/localizations.json

Requires: dash, plotly (``pip install dash plotly``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html


DRONE_COLORS = ["#1565c0", "#6a1b9a", "#00897b", "#ef6c00", "#5d4037"]


def _load(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def _make_map(entry: dict) -> go.Figure:
    src = entry["source"]
    cloud = entry["cloud_latlon"]

    fig = go.Figure()

    # Confidence cloud polygon. scattermapbox supports `fill="toself"` so
    # we close the ring and the polygon is rendered translucent red.
    cloud_lat = [p["lat"] for p in cloud] + [cloud[0]["lat"]]
    cloud_lon = [p["lon"] for p in cloud] + [cloud[0]["lon"]]
    fig.add_trace(go.Scattermapbox(
        lat=cloud_lat, lon=cloud_lon, mode="lines",
        line=dict(color="#c62828", width=2),
        fill="toself", fillcolor="rgba(198,40,40,0.20)",
        name=f"{int(entry['cloud_confidence'] * 100)}% confidence zone",
        hoverinfo="skip",
    ))

    # Drones
    for i, d in enumerate(entry["drones_used"]):
        col = DRONE_COLORS[i % len(DRONE_COLORS)]
        fig.add_trace(go.Scattermapbox(
            lat=[d["lat"]], lon=[d["lon"]], mode="markers+text",
            marker=dict(size=14, color=col),
            text=[d["drone_id"]],
            textposition="top right",
            name=d["drone_id"],
            hovertemplate=(
                f"<b>{d['drone_id']}</b><br>"
                f"lat={d['lat']:.6f}<br>"
                f"lon={d['lon']:.6f}<br>"
                f"σ_t={d['sigma_t_ms']:.2f} ms<br>"
                f"σ_pos={d['sigma_pos_m']:.1f} m"
                "<extra></extra>"
            ),
        ))

    # Source estimate — drawn as a white halo (large) + red dot (smaller)
    # on top, because the OpenStreetMap mapbox style only supports the
    # default circle marker; custom 'star'/'cross' symbols silently fall
    # back to a tiny dot and disappear behind the cloud polygon.
    fig.add_trace(go.Scattermapbox(
        lat=[src["lat"]], lon=[src["lon"]], mode="markers",
        marker=dict(size=10, color="white"),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scattermapbox(
        lat=[src["lat"]], lon=[src["lon"]], mode="markers+text",
        marker=dict(size=7, color="#c62828"),
        text=[f"  estimate ({entry['cep50_m']:.1f} m)"],
        textposition="middle right",
        textfont=dict(color="#c62828", size=11, family="Arial Black"),
        name="source (estimate)",
        hovertemplate=(
            f"<b>estimate</b><br>"
            f"lat={src['lat']:.6f}<br>"
            f"lon={src['lon']:.6f}<br>"
            f"CEP50={entry['cep50_m']} m"
            "<extra></extra>"
        ),
    ))

    # Choose a viewport that fits drones + cloud
    all_lats = [d["lat"] for d in entry["drones_used"]] + cloud_lat + [src["lat"]]
    all_lons = [d["lon"] for d in entry["drones_used"]] + cloud_lon + [src["lon"]]
    lat_c = (min(all_lats) + max(all_lats)) / 2
    lon_c = (min(all_lons) + max(all_lons)) / 2
    span = max(max(all_lats) - min(all_lats),
               (max(all_lons) - min(all_lons)) * 0.55, 0.002)
    # Convert lat span to a rough zoom level. Empirical: zoom 15 ≈ 0.005°
    zoom = max(11, min(17, 15 - 1.8 * (span / 0.005 - 1)))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=lat_c, lon=lon_c),
            zoom=zoom,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#ccc", borderwidth=1),
    )
    return fig


def _stat_card(label: str, value: str, color: str, suffix: str = "") -> html.Div:
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": "#888",
                               "textTransform": "uppercase",
                               "letterSpacing": "0.5px"}),
        html.Div(value, style={"fontSize": "24px", "fontWeight": "700",
                                "color": color, "lineHeight": "1.1"}),
        html.Div(suffix, style={"fontSize": "11px", "color": "#888"}),
    ], style={"textAlign": "center", "padding": "10px",
              "background": "#fafbfc", "borderRadius": "8px",
              "border": "1px solid #e8eaed",
              "flex": 1, "margin": "0 4px 8px"})


def build_app(localizations_path: Path) -> Dash:
    entries = _load(localizations_path)

    app = Dash(__name__, title="Triangulation Viewer")

    if not entries:
        app.layout = html.Div([
            html.H2("Triangulation Viewer"),
            html.P(f"No localisations in {localizations_path}. "
                   "Run python -m triangulation.locate first."),
        ], style={"padding": "20px",
                  "fontFamily": "-apple-system, BlinkMacSystemFont,"
                                " 'Segoe UI', Arial"})
        return app

    options = [{"label": f"{e['scenario']}  ({e['label']})",
                "value": i} for i, e in enumerate(entries)]

    app.layout = html.Div([
        html.Div([
            html.H2("Triangulation Viewer",
                    style={"margin": 0, "fontWeight": 600}),
            html.Div(f"Source: {localizations_path}",
                     style={"color": "#666", "fontSize": "12px"}),
        ], style={"padding": "14px 24px", "background": "#fff",
                  "borderBottom": "1px solid #e0e0e0"}),

        html.Div([
            html.Div([
                html.Label("Scenario",
                           style={"fontSize": "13px", "fontWeight": 600}),
                dcc.Dropdown(id="scenario-dropdown", options=options,
                             value=0, clearable=False,
                             style={"marginBottom": "14px"}),
                dcc.Graph(id="map",
                          config={"scrollZoom": True,
                                  "displaylogo": False},
                          style={"height": "calc(100vh - 220px)",
                                 "minHeight": "480px"}),
            ], style={"flex": 3, "padding": "12px", "minWidth": "560px"}),

            html.Div([
                html.Div([
                    _stat_card("CEP50", "—", "#c62828", "metres"),
                ], id="stats-row1", style={"display": "flex"}),
                html.Div([
                    _stat_card("Zone area", "—", "#ef6c00", "m² (95%)"),
                    _stat_card("GDOP", "—", "#6a1b9a", "axis ratio"),
                ], id="stats-row2", style={"display": "flex"}),
                html.Hr(style={"border": "none",
                               "borderTop": "1px solid #e0e0e0",
                               "margin": "10px 0"}),
                html.Div([
                    html.Div("Localisation result",
                             style={"fontSize": "11px", "color": "#888",
                                    "textTransform": "uppercase",
                                    "marginBottom": "6px"}),
                    html.Pre(id="info-pre",
                             style={"fontSize": "12px",
                                    "background": "#272822",
                                    "color": "#f8f8f2", "padding": "10px",
                                    "borderRadius": "6px",
                                    "maxHeight": "240px",
                                    "overflow": "auto", "margin": 0,
                                    "fontFamily":
                                        "Menlo, Consolas, monospace"}),
                ]),
            ], style={"flex": 1, "padding": "16px 18px",
                      "background": "#fff",
                      "borderLeft": "1px solid #e0e0e0",
                      "minWidth": "320px", "maxWidth": "420px"}),
        ], style={"display": "flex", "background": "#f8f9fa"}),
    ], style={"fontFamily":
                  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial",
              "minHeight": "100vh", "background": "#f8f9fa"})

    @app.callback(
        Output("map", "figure"),
        Output("stats-row1", "children"),
        Output("stats-row2", "children"),
        Output("info-pre", "children"),
        Input("scenario-dropdown", "value"),
    )
    def _render(idx: int):
        entry = entries[int(idx or 0)]
        fig = _make_map(entry)
        info = json.dumps({
            "scenario": entry["scenario"],
            "label": entry["label"],
            "source": entry["source"],
            "cep50_m": entry["cep50_m"],
            "cep95_m_approx": entry["cep95_m_approx"],
            "zone_area_m2": entry["zone_area_m2"],
            "gdop": entry["gdop"],
            "confidence": entry["localization_confidence"],
            "bearing_from_first_drone_deg":
                entry["bearing_from_first_drone_deg"],
            "distance_from_first_drone_m":
                entry["distance_from_first_drone_m"],
            "input_errors": entry["input_errors"],
        }, indent=2)
        row1 = [_stat_card("CEP50", f"{entry['cep50_m']:.2f}",
                            "#c62828", "metres")]
        row2 = [
            _stat_card("Zone area", f"{entry['zone_area_m2']:.0f}",
                       "#ef6c00", "m² (95%)"),
            _stat_card("GDOP", f"{entry['gdop']:.2f}",
                       "#6a1b9a", "axis ratio"),
        ]
        return fig, row1, row2, info

    return app


def _cli(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m triangulation.viewer")
    p.add_argument("path", nargs="?",
                   default="detection/output/localizations.json",
                   help="path to localizations.json")
    p.add_argument("--port", type=int, default=8060)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        print(f"error: {path} does not exist. "
              "Run 'python -m triangulation.locate' first.", file=sys.stderr)
        return 1
    app = build_app(path)
    print(f"Triangulation viewer on http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
