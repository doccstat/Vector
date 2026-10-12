# Vendored source revisions

This fork includes dependency sources directly; a recursive submodule checkout
is not required. The pins below correspond to upstream Vector
`ddeed8ca1ffedfaba7f4341b911089906862d5c4` (dependency/mirror update #989).
Submodule metadata is omitted; licenses and upstream source fixtures are retained.

| Path | Repository | Revision |
| --- | --- | --- |
| `external/apache/commons-lang` | [apache/commons-lang](https://github.com/apache/commons-lang) | `7b6048b7a9d1339a12d353cb85b2222df7bf5668` |
| `external/axml/manifest-editor` | [JingMatrix/ManifestEditor](https://github.com/JingMatrix/ManifestEditor) | `c238e28f3a1a0275c38945aa4f646b065d3f5889` |
| `external/dobby` | [JingMatrix/Dobby](https://github.com/JingMatrix/Dobby) | `05a09ac6807a6bb1726350e40ea4b127c1c79809` |
| `external/fmt` | [fmtlib/fmt](https://github.com/fmtlib/fmt) | `5da4e9a3fb15626ba92969199061e0169ebc8a00` |
| `external/lsplant` | [JingMatrix/LSPlant](https://github.com/JingMatrix/LSPlant) | `7a768e31ffb2852797631b5140b54f9702a78743` |
| `external/lsplt` | [JingMatrix/LSPlt](https://github.com/JingMatrix/LSPlt) | `a89012ef2d1dbc62b6fc205cb941f00a9c9a3d18` |
| `external/xz-embedded` | [tukaani-project/xz-embedded](https://github.com/tukaani-project/xz-embedded) | `ae63ae3a36ed01724674e8f3d750dc47bf125410` |
| `services/libxposed` | [JingMatrix/libxposed-service](https://github.com/JingMatrix/libxposed-service) | `3318940876192e29cf6ab07637e899e22a87ebf0` |
| `xposed/libxposed` | [JingMatrix/libxposed-api](https://github.com/JingMatrix/libxposed-api) | `39cac0845771547c9c67a3e3ce255af110a54a0e` |
| `external/lsplant/lsplant/src/main/jni/external/dex_builder` | [JingMatrix/DexBuilder](https://github.com/JingMatrix/DexBuilder) | `0c27690d88e217d1d2f0f53658cc140b43520b18` |
| `external/lsplant/lsplant/src/main/jni/external/dex_builder/external/parallel_hashmap` | [greg7mdp/parallel-hashmap](https://github.com/greg7mdp/parallel-hashmap) | `0cd57d29a959256ed66b2afdd1009928fc625d09` |
| `external/lsplant/docs/doxygen-awesome-css` | [jothepro/doxygen-awesome-css](https://github.com/jothepro/doxygen-awesome-css) | `df88fe4fdd97714fadfd3ef17de0b4401f804052` |

Both libxposed mirrors now provide the exact upstream pins; no substitute API
revision is used. When refreshing a dependency, preserve its nested vendored
trees and review local changes before replacing source files.
