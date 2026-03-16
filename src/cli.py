"""CLI entry point for the Tanzania Early Warning Bulletin Generator."""

import click
from pathlib import Path


@click.group()
def cli():
    """Tanzania Early Warning Bulletin Generator.

    Generate weather early warning bulletins in Word and PDF format.
    """
    pass


@cli.command()
@click.option('--input', '-i', 'input_path', required=True,
              type=click.Path(exists=True),
              help='Input JSON file with forecast data')
@click.option('--output-dir', '-o', default='./output',
              help='Output directory (default: ./output)')
@click.option('--format', '-f', 'output_format',
              type=click.Choice(['docx', 'pdf', 'both']), default='both',
              help='Output format (default: both)')
@click.option('--maps-dir', '-m', default=None,
              help='Base directory for pre-made map images')
@click.option('--no-maps', is_flag=True, default=False,
              help='Skip auto-map generation')
def generate_722e4(input_path, output_dir, output_format, maps_dir, no_maps):
    """Generate a 722E_4 Five Days Severe Weather Impact-Based Forecast."""
    from .pipeline import generate_722e4 as gen

    click.echo("=" * 60)
    click.echo("722E_4 Five Days Severe Weather Forecast Generator")
    click.echo("=" * 60)

    try:
        result = gen(
            input_path=input_path,
            output_dir=output_dir,
            output_format=output_format,
            maps_dir=maps_dir,
            auto_maps=not no_maps,
        )
        click.echo("\nGeneration complete!")
        for fmt, path in result.items():
            click.echo(f"  {fmt.upper()}: {path}")
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--input', '-i', 'input_path', required=True,
              type=click.Path(exists=True),
              help='Input JSON file with bulletin data')
@click.option('--output-dir', '-o', default='./output',
              help='Output directory (default: ./output)')
@click.option('--format', '-f', 'output_format',
              type=click.Choice(['docx', 'pdf', 'both']), default='both',
              help='Output format (default: both)')
@click.option('--maps-dir', '-m', default=None,
              help='Base directory for pre-made map images')
@click.option('--no-maps', is_flag=True, default=False,
              help='Skip auto-map generation')
def generate_multirisk(input_path, output_dir, output_format, maps_dir, no_maps):
    """Generate a Multirisk Three Days Impact-Based Forecast Bulletin."""
    from .pipeline import generate_multirisk as gen

    click.echo("=" * 60)
    click.echo("Tanzania Multirisk Bulletin Generator")
    click.echo("=" * 60)

    try:
        result = gen(
            input_path=input_path,
            output_dir=output_dir,
            output_format=output_format,
            maps_dir=maps_dir,
            auto_maps=not no_maps,
        )
        click.echo("\nGeneration complete!")
        for fmt, path in result.items():
            click.echo(f"  {fmt.upper()}: {path}")
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    cli()
