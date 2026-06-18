#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Minimal CryEngine CGF material-subset reader.

This is intentionally narrow: it reads the 0x746 chunk table and
MeshSubsets chunks so we can verify RC output material IDs without decoding a
full mesh.
"""

from dataclasses import dataclass
import os
import struct


CHUNK_TYPE_MESH = 0x1000
CHUNK_TYPE_MESH_SUBSETS = 0x1017
MESH_CHUNK_VERSION_0801 = 0x0801
MESH_SUBSETS_CHUNK_VERSION_0800 = 0x0800

CHUNK_TYPE_NAMES = {
    CHUNK_TYPE_MESH: "Mesh",
    0x100B: "Node",
    0x1013: "SourceInfo",
    0x1014: "MtlName",
    0x1015: "ExportFlags",
    0x1016: "DataStream",
    CHUNK_TYPE_MESH_SUBSETS: "MeshSubsets",
    0x1018: "MeshPhysicsData",
    0x1019: "ImportSettings",
    0x101B: "AssetMetadata",
}


@dataclass
class CGFChunk:
    chunk_type: int
    version: int
    chunk_id: int
    size: int
    offset: int
    big_endian: bool = False

    @property
    def type_name(self):
        return CHUNK_TYPE_NAMES.get(self.chunk_type, f"0x{self.chunk_type:04x}")

    def to_dict(self):
        return {
            "type": self.chunk_type,
            "type_name": self.type_name,
            "version": self.version,
            "chunk_id": self.chunk_id,
            "size": self.size,
            "offset": self.offset,
            "big_endian": self.big_endian,
        }


def _read_exact(file_obj, size):
    data = file_obj.read(size)
    if len(data) != size:
        raise ValueError("Unexpected end of CGF file")
    return data


def read_chunk_table(cgf_path):
    with open(cgf_path, "rb") as f:
        header = _read_exact(f, 16)
        signature, version, chunk_count, chunk_table_offset = struct.unpack("<4sIII", header)
        if signature != b"CrCh":
            raise ValueError(f"Unsupported CGF signature {signature!r}; only 0x746 CrCh files are supported")
        if version != 0x746:
            raise ValueError(f"Unsupported CGF chunk file version 0x{version:x}; expected 0x746")
        if chunk_count > 10_000_000:
            raise ValueError(f"Invalid CGF chunk count: {chunk_count}")

        f.seek(chunk_table_offset)
        chunks = []
        for _ in range(chunk_count):
            chunk_type, raw_version, chunk_id, size, offset = struct.unpack("<HHIII", _read_exact(f, 16))
            big_endian = bool(raw_version & 0x8000)
            version = raw_version & ~0x8000
            chunks.append(CGFChunk(chunk_type, version, chunk_id, size, offset, big_endian))

    return chunks


def _chunk_map(chunks):
    return {chunk.chunk_id: chunk for chunk in chunks}


def _read_chunk_data(cgf_path, chunk):
    file_size = os.path.getsize(cgf_path)
    if chunk.offset + chunk.size > file_size:
        raise ValueError(f"Chunk {chunk.chunk_id} extends beyond CGF file size")

    with open(cgf_path, "rb") as f:
        f.seek(chunk.offset)
        return _read_exact(f, chunk.size)


def read_mesh_chunk_summary(cgf_path, chunk):
    if chunk.chunk_type != CHUNK_TYPE_MESH:
        raise ValueError(f"Chunk {chunk.chunk_id} is not a Mesh chunk")
    if chunk.version not in (MESH_CHUNK_VERSION_0801, 0x0800):
        raise ValueError(f"Unsupported Mesh chunk version 0x{chunk.version:x}")
    if chunk.big_endian:
        raise ValueError("Big-endian CGF chunks are not supported by this reader")

    data = _read_chunk_data(cgf_path, chunk)
    if len(data) < 28:
        raise ValueError(f"Mesh chunk {chunk.chunk_id} is too small")

    n_flags, n_flags2, n_verts, n_indices, n_subsets, n_subsets_chunk_id, n_vert_anim_id = struct.unpack_from(
        "<7i", data, 0
    )
    return {
        "chunk_id": chunk.chunk_id,
        "flags": n_flags,
        "flags2": n_flags2,
        "verts": n_verts,
        "indices": n_indices,
        "subset_count": n_subsets,
        "subsets_chunk_id": n_subsets_chunk_id,
        "vert_anim_id": n_vert_anim_id,
    }


def read_mesh_subsets(cgf_path, chunk):
    if chunk.chunk_type != CHUNK_TYPE_MESH_SUBSETS:
        raise ValueError(f"Chunk {chunk.chunk_id} is not a MeshSubsets chunk")
    if chunk.version != MESH_SUBSETS_CHUNK_VERSION_0800:
        raise ValueError(f"Unsupported MeshSubsets chunk version 0x{chunk.version:x}")
    if chunk.big_endian:
        raise ValueError("Big-endian CGF chunks are not supported by this reader")

    data = _read_chunk_data(cgf_path, chunk)
    if len(data) < 16:
        raise ValueError(f"MeshSubsets chunk {chunk.chunk_id} is too small")

    n_flags, n_count, _reserved0, _reserved1 = struct.unpack_from("<4i", data, 0)
    subset_size = struct.calcsize("<5if3f")
    required_size = 16 + n_count * subset_size
    if required_size > len(data):
        raise ValueError(f"MeshSubsets chunk {chunk.chunk_id} is truncated")

    subsets = []
    offset = 16
    for subset_index in range(n_count):
        (
            first_index,
            num_indices,
            first_vert,
            num_verts,
            material_id,
            radius,
            center_x,
            center_y,
            center_z,
        ) = struct.unpack_from("<5if3f", data, offset)
        offset += subset_size
        subsets.append(
            {
                "subset": subset_index,
                "first_index": first_index,
                "num_indices": num_indices,
                "first_vert": first_vert,
                "num_verts": num_verts,
                "material_id": material_id,
                "radius": radius,
                "center": [center_x, center_y, center_z],
            }
        )

    return {
        "chunk_id": chunk.chunk_id,
        "flags": n_flags,
        "count": n_count,
        "subsets": subsets,
    }


def read_cgf_material_summary(cgf_path):
    chunks = read_chunk_table(cgf_path)
    chunks_by_id = _chunk_map(chunks)
    mesh_chunks = [chunk for chunk in chunks if chunk.chunk_type == CHUNK_TYPE_MESH]
    subset_chunks = [chunk for chunk in chunks if chunk.chunk_type == CHUNK_TYPE_MESH_SUBSETS]

    meshes = []
    for mesh_chunk in mesh_chunks:
        mesh = read_mesh_chunk_summary(cgf_path, mesh_chunk)
        subset_chunk = chunks_by_id.get(mesh["subsets_chunk_id"])
        if subset_chunk and subset_chunk.chunk_type == CHUNK_TYPE_MESH_SUBSETS:
            mesh["subsets"] = read_mesh_subsets(cgf_path, subset_chunk)["subsets"]
        else:
            mesh["subsets"] = []
        meshes.append(mesh)

    standalone_subset_chunks = [
        read_mesh_subsets(cgf_path, chunk)
        for chunk in subset_chunks
        if not any(mesh.get("subsets_chunk_id") == chunk.chunk_id for mesh in meshes)
    ]

    material_ids = sorted(
        {
            subset["material_id"]
            for mesh in meshes
            for subset in mesh.get("subsets", [])
            if subset.get("material_id") is not None
        }
    )

    return {
        "path": cgf_path,
        "file_version": "0x746",
        "chunk_count": len(chunks),
        "chunks": [chunk.to_dict() for chunk in chunks],
        "meshes": meshes,
        "standalone_mesh_subsets": standalone_subset_chunks,
        "material_ids": material_ids,
    }
