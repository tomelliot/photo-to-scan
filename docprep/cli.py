"""CLI for docprep."""

from pathlib import Path

import click
import cv2


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.argument("output_path", type=click.Path(path_type=Path))
@click.option("--debug", type=click.Path(path_type=Path), default=None,
              help="Directory for debug output images.")
def cli(input_path: Path, output_path: Path, debug: Path | None):
    """Detect, crop, and deskew a document from a photo."""
    from docprep.scan import scan_document

    img = cv2.imread(str(input_path))
    if img is None:
        raise click.ClickException(f"Could not read image: {input_path}")

    prefix = f"{input_path.stem}_" if debug else ""
    result = scan_document(img, debug_dir=debug, debug_prefix=prefix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), result)
    click.echo(f"{input_path.name} -> {output_path.name} ({result.shape[1]}x{result.shape[0]})")
