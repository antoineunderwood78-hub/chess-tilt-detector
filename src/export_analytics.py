import csv
import io
import os

import chess.pgn
import requests
import zstandard as zstd

from src.tilt import analyze_game_for_tilt

# URL of a Lichess dump
URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2025-11.pgn.zst"


def get_game_id(site_url):
    """Extracts game ID from Lichess URL."""
    if not site_url:
        return "unknown"
    return site_url.split("/")[-1]


def check_time_control(tc, mode):
    """Checks if time control matches the selected mode."""
    try:
        base = int(tc.split("+")[0])
        if mode == "Bullet":
            return base < 180
        elif mode == "Blitz":
            return 180 <= base <= 300
        elif mode == "Rapid":
            return 300 < base <= 900
        else:
            return False
    except:
        return False


def process_and_export_games(
    url,
    max_games=1000,
    output_dir="data/processed",
    time_control_mode="Blitz",
    progress_callback=None,
):
    """
    Streams games, analyzes them, and exports data to CSVs.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    metadata_file = os.path.join(output_dir, "games_metadata.csv")
    events_file = os.path.join(output_dir, "tilt_events.csv")

    # Initialize CSVs with headers
    with open(metadata_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["game_id", "white_elo", "black_elo", "time_control", "winner"])

    with open(events_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "game_id",
                "player_color",
                "player_elo",
                "tilt_start_move",
                "moves_survived",
                "has_lost",
            ]
        )

    print(f"Connecting to {url}...")
    if progress_callback:
        progress_callback(0, f"Connecting to {url}...")

    # Stream the response
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print(f"Failed to connect: {response.status_code}")
        return

    dctx = zstd.ZstdDecompressor()
    reader = dctx.stream_reader(response.raw)
    text_reader = io.TextIOWrapper(reader, encoding="utf-8")

    count = 0
    analyzed_count = 0

    print("Streaming and processing games...")
    if progress_callback:
        progress_callback(0, "Streaming and processing games...")

    while analyzed_count < max_games:
        game = chess.pgn.read_game(text_reader)
        if game is None:
            break

        count += 1
        if count % 1000 == 0:
            msg = f"Scanned {count} games (Analyzed: {analyzed_count})..."
            print(msg)
            if progress_callback:
                # Estimate progress based on analyzed count vs max_games
                # Note: This is imperfect as we don't know total games, but good enough for UI
                progress = min(analyzed_count / max_games, 1.0)
                progress_callback(progress, msg)

        headers = game.headers
        white_elo_str = headers.get("WhiteElo", "?")
        black_elo_str = headers.get("BlackElo", "?")
        time_control = headers.get("TimeControl", "?")
        site = headers.get("Site", "")
        result = headers.get("Result", "*")

        try:
            w_elo = int(white_elo_str)
            b_elo = int(black_elo_str)

            # Filter: Elo < 1500 and Time Control Mode
            if (
                w_elo < 1500
                and b_elo < 1500
                and check_time_control(time_control, time_control_mode)
            ):
                # Filter: Must have analysis
                has_analysis = False
                node = game
                # Check first 20 moves for analysis
                for _ in range(20):
                    node = node.next()
                    if node is None:
                        break
                    if (
                        node.comment
                        and "%eval" in node.comment
                        and "%clk" in node.comment
                    ):
                        has_analysis = True
                        break

                if not has_analysis:
                    continue

                analyzed_count += 1
                game_id = get_game_id(site)

                # Determine winner
                winner = "Draw"
                if result == "1-0":
                    winner = "White"
                elif result == "0-1":
                    winner = "Black"

                # Write to Metadata CSV
                with open(metadata_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([game_id, w_elo, b_elo, time_control, winner])

                # Analyze for Tilt
                # Calculate total moves first
                total_moves = game.end().ply() // 2

                # Analyze White
                white_tilts = analyze_game_for_tilt(game, True)
                for t in white_tilts:
                    has_lost = result == "0-1"  # White lost
                    moves_survived = total_moves - t["blunder_number"]
                    with open(events_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            [
                                game_id,
                                "White",
                                w_elo,
                                t["blunder_number"],
                                moves_survived,
                                has_lost,
                            ]
                        )

                # Analyze Black
                black_tilts = analyze_game_for_tilt(game, False)
                for t in black_tilts:
                    has_lost = result == "1-0"  # Black lost
                    moves_survived = total_moves - t["blunder_number"]
                    with open(events_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            [
                                game_id,
                                "Black",
                                b_elo,
                                t["blunder_number"],
                                moves_survived,
                                has_lost,
                            ]
                        )

                # Update progress for every analyzed game to be smoother
                if progress_callback:
                    progress = min(analyzed_count / max_games, 1.0)
                    progress_callback(
                        progress, f"Analyzed {analyzed_count}/{max_games} games"
                    )

        except ValueError:
            continue

    if progress_callback:
        progress_callback(1.0, f"Done! Exported {analyzed_count} games.")
    print(f"Done. Exported {analyzed_count} analyzed games.")


if __name__ == "__main__":
    process_and_export_games(URL, max_games=100, time_control_mode="Blitz")
