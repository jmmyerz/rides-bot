import munch
from pathlib import Path
from typing import Self

from . import cmdline


# Extending a Munch object for the sole purpose of adding load from / save to file functions
class Config(munch.Munch):

    def load(self, filename: Path) -> Self:
        with open(filename, 'r') as f:
            return self.fromYAML(f)

    def save(self, filename: Path) -> None:
        try:
            with open(filename, 'w') as f:
                munch.toYAML(
                    {key: val for key, val in self.items() if not key.startswith('_')},
                    stream=f,
                    sort_keys=False,
                )
            cmdline.logger(f'Saved config: {filename}', level='debug')
        except:
            raise Exception('Could not save config')


# Just some debugging
def debug() -> Config:
    f = (Path(__file__).parent / '../config.yaml').resolve()
    return Config().load(filename=f)


if __name__ == '__main__':
    config = debug()
    cmdline.logger(config, level='debug')
