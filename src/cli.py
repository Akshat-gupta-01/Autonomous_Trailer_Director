"""CLI entry point."""

from __future__ import annotations

import click
import os
from pathlib import Path

from src.pipeline import Pipeline
from src.config import load_config
from src.video_renderer import VideoRendererConfig
from src.providers import (
    BudgetController,
    BudgetConfig,
    FallbackChain,
    MockProvider,
    ReplayProvider,
    GeminiProvider,
    GeminiProviderOpenAICompat,
)


def _create_provider(pconfig: dict) -> object | None:
    """Create a provider instance from config dict."""
    provider_id = pconfig.get("provider_id")
    model = pconfig.get("model")
    api_key_env = pconfig.get("api_key_env")
    
    # Get API key from env if specified
    api_key = os.getenv(api_key_env) if api_key_env else None
    
    try:
        if provider_id == "gemini":
            # Use the native Gemini SDK provider
            return GeminiProvider(api_key=api_key, model=model or "gemini-1.5-pro")
        elif provider_id == "gemini-openai-compat":
            # Use OpenAI-compatible endpoint
            base_url = pconfig.get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")
            return GeminiProviderOpenAICompat(api_key=api_key, model=model or "gemini-1.5-pro", base_url=base_url)
        elif provider_id == "anthropic":
            # Placeholder for future Anthropic provider
            click.echo("Warning: Anthropic provider not yet implemented, skipping", err=True)
            return None
        elif provider_id == "openai":
            # Placeholder for future OpenAI provider
            click.echo("Warning: OpenAI provider not yet implemented, skipping", err=True)
            return None
        else:
            click.echo(f"Warning: Unknown provider '{provider_id}', skipping", err=True)
            return None
    except Exception as e:
        click.echo(f"Warning: Failed to create provider '{provider_id}': {e}", err=True)
        return None


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Config file path")
@click.option("--mock", is_flag=True, help="Run in mock mode (no API keys)")
@click.option("--replay", type=click.Path(exists=True, path_type=Path), help="Replay file for deterministic runs")
@click.pass_context
def cli(ctx, config, mock, replay):
    """Autonomous Trailer Director CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["mock"] = mock
    ctx.obj["replay_file"] = replay


@cli.command()
@click.option("--package", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Episode package path")
@click.option("--scenes", "-s", type=click.Path(exists=True, path_type=Path), help="Scene descriptions path")
@click.option("--dialogue", "-d", type=click.Path(exists=True, path_type=Path), help="Dialogue/subtitles path")
@click.option("--policies", type=click.Path(exists=True, path_type=Path), help="Rating policies path")
@click.option("--contracts", type=click.Path(exists=True, path_type=Path), help="Contracts path")
@click.option("--audiences", type=click.Path(exists=True, path_type=Path), help="Audience profiles path")
@click.option("--history", type=click.Path(exists=True, path_type=Path), help="Historic performance path")
@click.option("--costs", type=click.Path(exists=True, path_type=Path), help="Cost sheet path")
@click.option("--output", "-o", required=True, type=click.Path(path_type=Path), help="Output directory")
@click.option("--budget", type=float, help="Budget override (USD)")
@click.option("--render-video/--no-render-video", default=False, help="Render actual video files from EDL (requires ffmpeg)")
@click.option("--video-codec", default="libx264", help="Video codec for rendering")
@click.option("--video-crf", default=23, type=int, help="CRF quality (18-28, lower = better)")
@click.option("--video-preset", default="medium", help="ffmpeg preset (ultrafast to veryslow)")
@click.pass_context
def run(ctx, package, scenes, dialogue, policies, contracts, audiences, history, costs, output, budget, render_video, video_codec, video_crf, video_preset):
    """Run full pipeline: ingest -> plan -> verify -> emit EDL."""
    config = load_config(ctx.obj["config_path"])
    
    # Override budget if provided
    if budget:
        config["budget"]["total_usd"] = budget
    
    # Setup providers based on config
    providers_list = []
    
    if ctx.obj["mock"]:
        providers_list.append(MockProvider())
    elif ctx.obj["replay_file"]:
        providers_list.append(ReplayProvider(str(ctx.obj["replay_file"])))
    else:
        # Build providers from config
        for pconfig in config.get("providers", []):
            provider = _create_provider(pconfig)
            if provider:
                providers_list.append(provider)
        
        # Fallback to mock if no providers configured
        if not providers_list:
            providers_list.append(MockProvider())
    
    # Create fallback chain
    fallback = FallbackChain(providers_list)
    
    # Budget controller
    budget_config = BudgetConfig(**config["budget"])
    budget_controller = BudgetController(budget_config)
    
    # Create pipeline
    video_config = VideoRendererConfig(
        video_codec=video_codec,
        crf=video_crf,
        preset=video_preset,
    )
    pipeline = Pipeline(
        model_provider=fallback,
        budget_controller=budget_controller,
        config=config,
        output_dir=output,
        mock_mode=ctx.obj["mock"],
        render_video=render_video,
        video_config=video_config,
    )
    
    click.echo(f"Running pipeline with episode package: {package}")
    click.echo(f"Output directory: {output}")
    
    result = pipeline.run(
        episode_package_path=package,
        scene_descriptions_path=scenes,
        dialogue_path=dialogue,
        policies_path=policies,
        contracts_path=contracts,
        audience_profiles_path=audiences,
        historic_data_path=history,
        cost_sheet_path=costs,
    )
    
    # Print summary
    click.echo("\n=== Pipeline Complete ===")
    click.echo(f"Story map: {len(result.story_map.scenes)} scenes, {len(result.story_map.entities)} entities")
    click.echo(f"Spoiler facts: {len(result.spoiler_facts)}")
    click.echo(f"Rules compiled: {len(result.rules)}")
    click.echo(f"Trailers generated: {len(result.trailers)}")
    
    for trailer in result.trailers:
        status = trailer.validation.status.value if trailer.validation else "PENDING"
        click.echo(f"  {trailer.trailer_id} ({trailer.audience}): {status}, {trailer.duration_seconds:.1f}s, {len(trailer.segments)} segments")
    
    click.echo(f"\nTotal cost: ${result.cost_ledger.total_cost:.4f}")
    click.echo(f"Budget remaining: ${result.cost_ledger.budget_remaining:.4f}")
    click.echo(f"Outputs written to: {output}")


@cli.command()
@click.option("--plans", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Plans directory")
@click.pass_context
def verify(ctx, plans):
    """Verify existing trailer plans."""
    click.echo(f"Verifying plans in: {plans}")
    # Would load and verify plans
    click.echo("Verification not yet implemented")


@cli.command()
@click.option("--event", "-e", required=True, type=click.Path(exists=True, path_type=Path), help="Change event JSON file")
@click.option("--plans", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Plans directory")
@click.pass_context
def apply_change(ctx, event, plans):
    """Apply a change event to existing plans."""
    click.echo(f"Applying change event: {event}")
    click.echo(f"To plans in: {plans}")
    # Would load event and apply
    click.echo("Change handling not yet implemented")


@cli.command()
@click.option("--session", "-s", required=True, type=click.Path(exists=True, path_type=Path), help="Replay session file")
@click.pass_context
def replay(ctx, session):
    """Replay a recorded session."""
    click.echo(f"Replaying session: {session}")
    click.echo("Replay not yet implemented")


@cli.command()
@click.option("--plans", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Plans directory")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output report path")
@click.pass_context
def report(ctx, plans, output):
    """Generate validation report."""
    click.echo(f"Generating report for: {plans}")
    if output:
        click.echo(f"Writing to: {output}")
    click.echo("Report generation not yet implemented")


if __name__ == "__main__":
    cli()