#!/usr/bin/env python3

import argparse
import numpy as np
import matplotlib.pyplot as plt
from plyfile import PlyData


def read_ply(filename):
    """
    Read a triangular mesh from an ASCII or binary PLY file.

    Only the vertex and face elements are used. Any additional PLY elements,
    such as an explicit edge element, are ignored.

    Returns
    -------
    vertices : (N, 3) ndarray
        Vertex coordinates.
    triangles : (M, 3) ndarray
        Triangle vertex indices.
    """
    ply = PlyData.read(filename)

    # ------------------------------------------------------------------
    # Vertices
    # ------------------------------------------------------------------
    if "vertex" not in ply:
        raise RuntimeError("PLY file contains no vertex element.")

    vertex_data = ply["vertex"].data

    required_vertex_properties = {"x", "y", "z"}
    available_vertex_properties = set(vertex_data.dtype.names)

    missing = required_vertex_properties - available_vertex_properties
    if missing:
        raise RuntimeError(
            "PLY vertex element is missing properties: "
            + ", ".join(sorted(missing))
        )

    vertices = np.column_stack((
        vertex_data["x"],
        vertex_data["y"],
        vertex_data["z"]
    )).astype(np.float64)

    # ------------------------------------------------------------------
    # Faces
    # ------------------------------------------------------------------
    if "face" not in ply:
        raise RuntimeError("PLY file contains no face element.")

    face_data = ply["face"].data
    property_names = face_data.dtype.names

    face_property = None

    # Common names used by PLY writers.
    for candidate in (
        "vertex_indices",
        "vertex_index",
        "vertex_ids",
        "vertices"
    ):
        if candidate in property_names:
            face_property = candidate
            break

    if face_property is None:
        raise RuntimeError(
            "Could not find a vertex-index property in the PLY faces.\n"
            f"Available face properties: {property_names}"
        )

    triangles = []

    for face in face_data[face_property]:
        indices = np.asarray(face, dtype=np.int64)

        if len(indices) != 3:
            raise RuntimeError(
                "Input mesh is not fully triangulated. "
                f"Found a face with {len(indices)} vertices."
            )

        triangles.append(indices)

    if not triangles:
        raise RuntimeError("PLY file contains no faces.")

    triangles = np.asarray(triangles, dtype=np.int64)

    # ------------------------------------------------------------------
    # Validate face indices.
    # ------------------------------------------------------------------
    if np.any(triangles < 0) or np.any(triangles >= len(vertices)):
        raise RuntimeError(
            "PLY contains a face referencing an invalid vertex index."
        )

    return vertices, triangles


def compute_edge_lengths(vertices, triangles):
    """
    Compute the length of every unique mesh edge.

    Each undirected edge is counted exactly once.
    """
    edges = set()

    for tri in triangles:
        a, b, c = map(int, tri)

        edges.add(tuple(sorted((a, b))))
        edges.add(tuple(sorted((b, c))))
        edges.add(tuple(sorted((c, a))))

    lengths = np.empty(len(edges), dtype=np.float64)

    for i, (a, b) in enumerate(edges):
        d = vertices[b] - vertices[a]
        lengths[i] = np.linalg.norm(d)

    return lengths


def compute_triangle_angles(vertices, triangles):
    """
    Compute all three interior angles of every triangle in degrees.

    Returns
    -------
    angles : ndarray
        One entry for each triangle corner, so the result contains
        3 * number_of_triangles values.
    """
    angles = []

    for tri in triangles:
        ia, ib, ic = map(int, tri)

        a = vertices[ia]
        b = vertices[ib]
        c = vertices[ic]

        # --------------------------------------------------------------
        # Angle at a
        # --------------------------------------------------------------
        ab = b - a
        ac = c - a

        # --------------------------------------------------------------
        # Angle at b
        # --------------------------------------------------------------
        ba = a - b
        bc = c - b

        # --------------------------------------------------------------
        # Angle at c
        # --------------------------------------------------------------
        ca = a - c
        cb = b - c

        def angle(u, v):
            nu = np.linalg.norm(u)
            nv = np.linalg.norm(v)

            if nu <= 1e-15 or nv <= 1e-15:
                return np.nan

            cos_theta = np.dot(u, v) / (nu * nv)

            # Protect against tiny floating-point errors.
            cos_theta = np.clip(cos_theta, -1.0, 1.0)

            return np.degrees(np.arccos(cos_theta))

        angles.append(angle(ab, ac))
        angles.append(angle(ba, bc))
        angles.append(angle(ca, cb))

    angles = np.asarray(angles, dtype=np.float64)

    return angles[np.isfinite(angles)]


def print_statistics(name, values):
    """
    Print basic statistics for a set of measurements.
    """
    print()
    print(name)
    print("-" * len(name))

    print(f"Count   : {len(values)}")
    print(f"Minimum : {np.min(values):.6f}")
    print(f"Maximum : {np.max(values):.6f}")
    print(f"Mean    : {np.mean(values):.6f}")
    print(f"Median  : {np.median(values):.6f}")
    print(f"Std dev : {np.std(values):.6f}")


def plot_angle_histogram(angles, bins, output):
    """
    Create and save the triangle-angle histogram.
    """
    plt.figure(figsize=(10, 4))

    plt.hist(
        angles,
        bins=bins,
        range=(0.0, 180.0)
    )

    # Equilateral triangle reference angle.
    plt.axvline(
        60.0,
        linestyle="--",
        linewidth=1.5,
        label="Target = 60°"
    )

    plt.xlim(0.0, 180.0)

    plt.xlabel("Angle (degrees)")
    plt.ylabel("Count")
    plt.title("Triangle Angle Distribution")

    plt.legend()

    plt.tight_layout()
    plt.savefig(output, dpi=300)
    plt.close()

    print(f"Saved: {output}")


def plot_edge_histogram(edge_lengths, bins, output, target_edge=None):
    """
    Create and save the edge-length histogram.
    """
    plt.figure(figsize=(10, 4))

    plt.hist(
        edge_lengths,
        bins=bins
    )

    if target_edge is not None:
        plt.axvline(
            target_edge,
            linestyle="--",
            linewidth=1.5,
            label=f"Target = {target_edge:g}"
        )

        plt.legend()

    plt.xlabel("Edge length")
    plt.ylabel("Count")
    plt.title("Edge Length Distribution")

    plt.tight_layout()
    plt.savefig(output, dpi=300)
    plt.close()

    print(f"Saved: {output}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compute triangle-angle and edge-length distributions "
            "from a triangular PLY mesh."
        )
    )

    parser.add_argument(
        "input",
        help="Input ASCII or binary PLY mesh"
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=100,
        help="Number of histogram bins (default: 100)"
    )

    parser.add_argument(
        "--target-edge",
        type=float,
        default=None,
        help="Optional target edge length to display on the histogram"
    )

    parser.add_argument(
        "--prefix",
        default="mesh",
        help="Prefix used for output histogram filenames"
    )

    args = parser.parse_args()

    if args.bins <= 0:
        raise RuntimeError("--bins must be positive.")

    # ------------------------------------------------------------------
    # Read mesh.
    # ------------------------------------------------------------------
    vertices, triangles = read_ply(args.input)

    print(f"Input: {args.input}")
    print(f"Vertices : {len(vertices)}")
    print(f"Triangles: {len(triangles)}")

    # ------------------------------------------------------------------
    # Compute measurements.
    # ------------------------------------------------------------------
    edge_lengths = compute_edge_lengths(
        vertices,
        triangles
    )

    angles = compute_triangle_angles(
        vertices,
        triangles
    )

    print(f"Unique edges: {len(edge_lengths)}")

    print_statistics(
        "Edge Lengths",
        edge_lengths
    )

    print_statistics(
        "Triangle Angles (degrees)",
        angles
    )

    # ------------------------------------------------------------------
    # Histograms.
    # ------------------------------------------------------------------
    angle_output = f"{args.prefix}_angles.png"
    edge_output = f"{args.prefix}_edge_lengths.png"

    plot_angle_histogram(
        angles,
        args.bins,
        angle_output
    )

    plot_edge_histogram(
        edge_lengths,
        args.bins,
        edge_output,
        args.target_edge
    )


if __name__ == "__main__":
    main()