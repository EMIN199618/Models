import { deflateRawSync } from "node:zlib";

/**
 * Seed üçün nümunə fayl generatorları.
 * Xarici asılılıq olmadan real, açıla bilən fayllar yaradır.
 */

// --- GLB (binar glTF) -------------------------------------------------------

/** Sadə düzbucaqlı prizma şəklində .glb yaradır — 3D önizləmə nümunəsi üçün. */
export function makeBoxGlb(
  size: { x: number; y: number; z: number },
  color: [number, number, number],
): Buffer {
  const hx = size.x / 2;
  const hy = size.y / 2;
  const hz = size.z / 2;

  // 8 təpə
  const positions = new Float32Array([
    -hx, -hy, -hz, hx, -hy, -hz, hx, hy, -hz, -hx, hy, -hz,
    -hx, -hy, hz, hx, -hy, hz, hx, hy, hz, -hx, hy, hz,
  ]);

  // 12 üçbucaq
  const indices = new Uint16Array([
    0, 2, 1, 0, 3, 2, // arxa
    4, 5, 6, 4, 6, 7, // ön
    0, 1, 5, 0, 5, 4, // alt
    3, 7, 6, 3, 6, 2, // üst
    0, 4, 7, 0, 7, 3, // sol
    1, 2, 6, 1, 6, 5, // sağ
  ]);

  const indexBytes = Buffer.from(indices.buffer, indices.byteOffset, indices.byteLength);
  const indexPadded = pad4(indexBytes);
  const positionBytes = Buffer.from(
    positions.buffer,
    positions.byteOffset,
    positions.byteLength,
  );
  const bin = pad4(Buffer.concat([indexPadded, positionBytes]));

  const gltf = {
    asset: { version: "2.0", generator: "arxvia-seed" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0 }],
    meshes: [
      {
        primitives: [{ attributes: { POSITION: 1 }, indices: 0, material: 0 }],
      },
    ],
    materials: [
      {
        pbrMetallicRoughness: {
          baseColorFactor: [...color, 1],
          metallicFactor: 0.05,
          roughnessFactor: 0.65,
        },
      },
    ],
    accessors: [
      { bufferView: 0, componentType: 5123, count: indices.length, type: "SCALAR" },
      {
        bufferView: 1,
        componentType: 5126,
        count: 8,
        type: "VEC3",
        min: [-hx, -hy, -hz],
        max: [hx, hy, hz],
      },
    ],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: indexBytes.length, target: 34963 },
      {
        buffer: 0,
        byteOffset: indexPadded.length,
        byteLength: positionBytes.length,
        target: 34962,
      },
    ],
    buffers: [{ byteLength: bin.length }],
  };

  const jsonChunk = pad4(Buffer.from(JSON.stringify(gltf), "utf8"), 0x20);

  const header = Buffer.alloc(12);
  header.write("glTF", 0, "ascii");
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + jsonChunk.length + 8 + bin.length, 8);

  const jsonHeader = Buffer.alloc(8);
  jsonHeader.writeUInt32LE(jsonChunk.length, 0);
  jsonHeader.writeUInt32LE(0x4e4f534a, 4); // "JSON"

  const binHeader = Buffer.alloc(8);
  binHeader.writeUInt32LE(bin.length, 0);
  binHeader.writeUInt32LE(0x004e4942, 4); // "BIN\0"

  return Buffer.concat([header, jsonHeader, jsonChunk, binHeader, bin]);
}

function pad4(buf: Buffer, fill = 0): Buffer {
  const remainder = buf.length % 4;
  if (remainder === 0) return buf;
  return Buffer.concat([buf, Buffer.alloc(4 - remainder, fill)]);
}

// --- ZIP --------------------------------------------------------------------

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(buf: Buffer): number {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** Tək fayllıq, həqiqi (açıla bilən) ZIP arxivi yaradır. */
export function makeZip(fileName: string, content: string): Buffer {
  const nameBytes = Buffer.from(fileName, "utf8");
  const raw = Buffer.from(content, "utf8");
  const compressed = deflateRawSync(raw);
  const crc = crc32(raw);

  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(20, 4); // version needed
  local.writeUInt16LE(0, 6); // flags
  local.writeUInt16LE(8, 8); // deflate
  local.writeUInt16LE(0, 10); // time
  local.writeUInt16LE(0x21, 12); // date (1980-01-01)
  local.writeUInt32LE(crc, 14);
  local.writeUInt32LE(compressed.length, 18);
  local.writeUInt32LE(raw.length, 22);
  local.writeUInt16LE(nameBytes.length, 26);
  local.writeUInt16LE(0, 28);

  const localBlock = Buffer.concat([local, nameBytes, compressed]);

  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(20, 4); // version made by
  central.writeUInt16LE(20, 6); // version needed
  central.writeUInt16LE(0, 8);
  central.writeUInt16LE(8, 10);
  central.writeUInt16LE(0, 12);
  central.writeUInt16LE(0x21, 14);
  central.writeUInt32LE(crc, 16);
  central.writeUInt32LE(compressed.length, 20);
  central.writeUInt32LE(raw.length, 24);
  central.writeUInt16LE(nameBytes.length, 28);
  central.writeUInt16LE(0, 30); // extra
  central.writeUInt16LE(0, 32); // comment
  central.writeUInt16LE(0, 34); // disk
  central.writeUInt16LE(0, 36); // internal attrs
  central.writeUInt32LE(0, 38); // external attrs
  central.writeUInt32LE(0, 42); // local header offset

  const centralBlock = Buffer.concat([central, nameBytes]);

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(1, 8);
  eocd.writeUInt16LE(1, 10);
  eocd.writeUInt32LE(centralBlock.length, 12);
  eocd.writeUInt32LE(localBlock.length, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([localBlock, centralBlock, eocd]);
}
