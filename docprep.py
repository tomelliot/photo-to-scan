"""Document image preprocessing CLI for Paperless-ngx."""

from pathlib import Path

import click
import cv2


@click.group()
def cli():
    """Document image preprocessing tools."""


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.argument("output_path", type=click.Path(path_type=Path))
def grayscale(input_path: Path, output_path: Path):
    """Convert an image to grayscale."""
    img = cv2.imread(str(input_path))
    if img is None:
        raise click.ClickException(f"Could not read image: {input_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(str(output_path), gray)
    click.echo(f"{input_path.name} -> {output_path.name} ({gray.shape[1]}x{gray.shape[0]})")


if __name__ == "__main__":
    cli()
