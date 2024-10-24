# type: ignore
# Data science libraries has no idea what convention is anyway

import io
import itertools
import os
import subprocess
import warnings
import webbrowser
from pathlib import Path

import folium
import osmnx
from osmnx import geocoder


root = Path(__file__).parent.resolve()
data = root / "data"
data.mkdir(parents=True, exist_ok=True)


place = input("Enter search location: ")
print("Loading map data...")


gdf = geocoder.geocode_to_gdf(place)

# Load graph from local file if possible
graph_path = data / f"{gdf['osm_id'][0]}.graphml"
try:
    graph = osmnx.load_graphml(graph_path)
except FileNotFoundError:
    graph = osmnx.graph_from_place(place, network_type="drive")
    osmnx.save_graphml(graph, graph_path)
else:
    print(f"Restored data from {graph_path}")


coordinates = [
    [gdf.bbox_south[0], gdf.bbox_west[0]],
    [gdf.bbox_north[0], gdf.bbox_east[0]],
]
print("SW-NE:", coordinates)
print("Number of nodes:", graph.number_of_nodes())
print("Number of edges:", graph.number_of_edges())


selection_map = folium.Map(location=[gdf.lat[0], gdf.lon[0]])
selection_map.fit_bounds(coordinates)
selection_map.add_child(folium.GeoJson(gdf.unary_union))
selection_map.add_child(folium.LatLngPopup())


map_path = data / f"map-{os.getpid()}.html"
selection_map.save(map_path)
webbrowser.open(f"file://{map_path}")


while True:
    print("\nCopy and paste coordinates of the source and destination points (Ctrl-C to terminate):")

    try:
        source_lon = float(input("Source longitude: "))
        source_lat = float(input("Source latitude: "))
        source_index = osmnx.nearest_nodes(graph, source_lon, source_lat)
        print("Got source", graph.nodes[source_index])

        destination_lon = float(input("Destination longitude: "))
        destination_lat = float(input("Destination latitude: "))
        destination_index = osmnx.nearest_nodes(graph, destination_lon, destination_lat)
        print("Got destination", graph.nodes[destination_index])

    except KeyboardInterrupt:
        print("\nTerminated")
        break

    if source_index == destination_index:
        warnings.warn("Source and destination are the same!")

    # Construct stdin stream for subprocess
    stdin = io.StringIO()
    stdin.write(f"{graph.number_of_nodes()} {graph.number_of_edges()} {source_index} {destination_index}\n")

    for index, node in graph.nodes(data=True):
        stdin.write(f"{index} {node['y']} {node['x']}\n")

    for u, v, *_ in graph.edges(data=True):
        stdin.write(f"{u} {v}\n")

    # Construct route map
    route_map = folium.Map(location=[gdf.lat[0], gdf.lon[0]])
    route_map.fit_bounds(coordinates)
    route_map.add_child(folium.GeoJson(gdf.unary_union))
    route_map.add_child(folium.LatLngPopup())
    route_map.add_child(
        folium.Marker(
            location=(source_lat, source_lon),
            tooltip="Source",
        )
    )
    route_map.add_child(
        folium.Marker(
            location=(destination_lat, destination_lon),
            tooltip="Destination",
        )
    )

    # Folium route colors
    colors = itertools.cycle(
        [
            "red",
            "blue",
            "gray",
            "darkred",
            "lightred",
            "orange",
            "beige",
            "green",
            "darkgreen",
            "lightgreen",
            "darkblue",
            "lightblue",
            "purple",
            "darkpurple",
            "pink",
            "cadetblue",
            "lightgray",
            "black",
        ],
    )

    for exec in ("a_star", "bfs"):
        executable = root.joinpath("build", f"{exec}.exe").resolve()
        print(f"Starting subprocess \"{executable}\"")

        process = subprocess.Popen(
            [executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdin.seek(0)
        stdout, stderr = process.communicate(stdin.read())
        print(f"Subprocess {executable} completed with return code {process.returncode}")

        if process.returncode == 0:
            stdout = stdout.strip()
            stderr = stderr.strip()

            if len(stderr) > 0:
                print("Extra info from subprocess:")
                print(stderr)

            route = list(map(int, stdout.split()))
            coordinates = []
            for index in route:
                node = graph.nodes[index]
                coordinates.append((node["y"], node["x"]))

            route_map.add_child(folium.PolyLine(locations=coordinates, tooltip=exec, color=next(colors), weight=5))

            # graph_route_path = data / f"route-{process.pid}.png"
            # osmnx.plot_graph_route(graph, route, filepath=graph_route_path, save=True, show=False, close=True)
            # print(f"Saved route graph to {graph_route_path}")

    route_path = data / f"route-{os.getpid()}.html"
    route_map.save(route_path)

    print("Displaying route map")
    webbrowser.open(f"file://{route_path}")
