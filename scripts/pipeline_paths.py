"""Shared paths for research scripts. Game inputs are always read-only."""
import os
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('NOVA_WORK_DIR', REPOSITORY)).resolve()
GAME = Path(os.environ.get('NOVA_GAME_DIR', 'D:/TapTap/PC Games/733498')).resolve()
CLI = Path(os.environ.get('VGMSTREAM_CLI', REPOSITORY/'tools/vgmstream/vgmstream-cli.exe'))


def protect_output(output, game=GAME):
    output, game = Path(output).resolve(), Path(game).resolve()
    if output == game or game in output.parents or output in game.parents:
        raise ValueError(f'Output and game directory must be disjoint: {output}, {game}')
    return output


protect_output(ROOT)
