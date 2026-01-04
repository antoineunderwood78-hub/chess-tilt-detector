import re


def parse_comment(comment):
    """
    Extracts evaluation and clock time from a PGN comment.
    Example comment: [%eval 0.17] [%clk 0:00:30]
    Returns: dict with 'eval' (float, centipawns) and 'clk' (int, seconds)
    """
    if not comment:
        return {}

    data = {}

    # Extract Eval
    # Patterns: [%eval 0.17] or [%eval #3] (mate in 3)
    eval_match = re.search(r"\[%eval\s+([#-]?\d+\.?\d*)\]", comment)
    if eval_match:
        val_str = eval_match.group(1)
        if "#" in val_str:
            # Mate score. We can treat it as a very high number.
            # It's a mate score!
            # #3 means White mates in 3 -> Huge positive eval
            # #-2 means Black mates in 2 -> Huge negative eval
            try:
                mate_in = int(val_str.replace("#", ""))
                # We use 10000 as a "virtual" mate score.
                # We subtract/add the distance to mate to prioritize faster mates.
                if mate_in > 0:
                    eval_val = 10000 - (mate_in * 100)
                else:
                    eval_val = -10000 - (mate_in * 100)  # mate_in is negative here
            except ValueError:
                eval_val = None
        else:
            try:
                # Standard eval in pawns, convert to centipawns
                eval_val = int(float(val_str) * 100)
            except ValueError:
                eval_val = None

        data["eval"] = eval_val

    # Extract Clock
    # Pattern: [%clk 0:00:30] or [%clk 0:05:00] or [%clk 0:00:30.5]
    # We use a loose regex to capture H:M:S
    clk_match = re.search(r"\[%clk\s+(\d+):(\d+):(\d+)(?:\.\d+)?\]", comment)
    if clk_match:
        h, m, s = map(int, clk_match.groups())
        total_seconds = h * 3600 + m * 60 + s
        data["clk"] = total_seconds

    return data
