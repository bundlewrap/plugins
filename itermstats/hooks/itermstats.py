from base64 import b64encode
from os import environ, remove
from tempfile import NamedTemporaryFile

try:
    import cairosvg
    from pygal import Config, Pie
    from pygal.style import Style
    IMPORTS = True
except ImportError:
    IMPORTS = False

from blockwart.utils import LOG

STYLE = Style(
    background='transparent',
    opacity=1,
    plot_background='transparent',
    colors=('#00ae19', '#25ff44', '#ffde00', '#c90000'),
)

def node_apply_end(repo, node, duration=None, interactive=None, result=None, **kwargs):
    if environ.get('TERM_PROGRAM', None) != "iTerm.app" or not interactive:
        LOG.debug("skipping iTerm stats (wrong terminal)")
        return

    if not IMPORTS:
        LOG.error("failed to import dependencies of itermstats plugin")
        return

    css_file = NamedTemporaryFile(delete=False)
    css_file.write(".text-overlay { display: none; }")
    css_file.close()

    config = Config(
        height=150,
        style=STYLE,
        width=350,
    )
    config.css.append(css_file.name)

    chart = Pie(config)
    chart.add('correct', result.correct)
    chart.add('fixed', result.fixed)
    chart.add('skipped', result.skipped)
    chart.add('failed', result.failed)

    png_data = cairosvg.svg2png(bytestring=chart.render())
    png_data_b64 = b64encode(png_data)

    remove(css_file.name)

    print("\033]1337;File=inline=1:{}\007".format(png_data_b64))
