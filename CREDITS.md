# Créditos

- **Linguagem visual** inspirada no [editonny](https://github.com/soumatheusgomes/editonny), de Matheus Gomes (licença MIT): tokens de cor (ink/fog, laranja `#ff4f12`, volt `#d4ff3a`) e escolhas tipográficas do `DESIGN.md`. Nenhum código, cena, vídeo, áudio ou imagem do editonny foi copiado; as cenas deste projeto foram escritas do zero.
- **Figtree** — Erik Kennedy, SIL Open Font License 1.1 (`fonts/figtree_OFL.txt`).
- **Anton** — Vernon Adams, SIL Open Font License 1.1 (`fonts/anton_OFL.txt`).
- **GSAP 3.13** — GreenSock, licença padrão gratuita; baixado em tempo de execução de cdn.jsdelivr.net (não é redistribuído aqui).
- **Ícones** — desenhados para este projeto (`engine/icons.js`).
- **Trilha e efeitos sonoros** — sintetizados em código (`videobot/audio.py`).

## Three.js

- Three.js 0.160.0 — licença MIT — https://threejs.org — baixado automaticamente para `engine/vendor/` (usado no modo 3D, `visual.cena3d`).
- Extras do Three.js 0.160.0 (GLTFLoader, SkeletonUtils, BufferGeometryUtils, RoomEnvironment, RoundedBoxGeometry) — licença MIT — baixados para `engine/vendor/three-extras.js` e convertidos de módulo ES para script comum (`videobot/util.py`).

## Modelos 3D

- **RobotExpressive** — modelo de Tomás Laulhé (Quaternius), modificações de Don McCurdy — **CC0 1.0** (domínio público). Baixado do repositório do Three.js para `engine/vendor/modelos3d.js`; recolorido com a paleta do vídeo e com sombreado suavizado.
