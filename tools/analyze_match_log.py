#!/usr/bin/env python3
"""
Analyze match debug logs to identify AI improvement opportunities.

Usage:
    python tools/analyze_match_log.py <log_file_path>
"""

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parse_log_file(log_path):
    """Parse the debug log and extract key metrics."""
    
    events = []
    event_types = Counter()
    
    # Track specific metrics
    shots = []
    passes = []
    tackles = []
    possessions = []
    goals = []
    
    # Track player behavior patterns
    player_decisions = defaultdict(list)
    player_passes = defaultdict(int)
    player_shots = defaultdict(int)
    
    with open(log_path, 'r') as f:
        for line in f:
            # Extract timestamp, event type, and details
            match = re.search(r'Time: ([\d.]+)s.*Event: (\w+).*Details: (.+)$', line)
            if not match:
                continue
                
            time, event_type, details = match.groups()
            time = float(time)
            
            event_types[event_type] += 1
            events.append((time, event_type, details))
            
            # Parse specific event types
            if event_type == 'shot' or event_type == 'shot_attempt':
                shots.append((time, details))
                player_match = re.search(r'Player (\d+)', details)
                if player_match:
                    player_shots[player_match.group(1)] += 1
                    
            elif event_type == 'pass':
                passes.append((time, details))
                player_match = re.search(r'#(\d+)', details)
                if player_match:
                    player_passes[player_match.group(1)] += 1
                    
            elif event_type == 'tackle':
                tackles.append((time, details))
                
            elif event_type == 'team_possession':
                possessions.append((time, details))
                
            elif event_type == 'goal':
                goals.append((time, details))
                
            elif event_type == 'decision':
                player_match = re.search(r'#(\d+)', details)
                if player_match:
                    player_decisions[player_match.group(1)].append((time, details))
    
    return {
        'events': events,
        'event_types': event_types,
        'shots': shots,
        'passes': passes,
        'tackles': tackles,
        'possessions': possessions,
        'goals': goals,
        'player_decisions': player_decisions,
        'player_passes': player_passes,
        'player_shots': player_shots,
    }


def analyze_shooting_behavior(shots):
    """Analyze shooting patterns for realism issues."""
    print("\n=== SHOOTING BEHAVIOR ANALYSIS ===")
    print(f"Total shots: {len(shots)}")
    
    if not shots:
        print("  ⚠️  No shots detected - AI may be too conservative")
        return
    
    # Analyze shot timing
    shot_times = [t for t, _ in shots]
    if len(shot_times) > 1:
        intervals = [shot_times[i+1] - shot_times[i] for i in range(len(shot_times)-1)]
        avg_interval = sum(intervals) / len(intervals)
        print(f"  Average time between shots: {avg_interval:.1f}s")
    
    # Check for shot details
    on_target_count = 0
    distance_stats = []
    power_stats = []
    
    for time, details in shots:
        if 'on_target=True' in details:
            on_target_count += 1
        
        dist_match = re.search(r'distance=([\d.]+)m', details)
        if dist_match:
            distance_stats.append(float(dist_match.group(1)))
            
        power_match = re.search(r'power=([\d.]+)', details)
        if power_match:
            power_stats.append(float(power_match.group(1)))
    
    if distance_stats:
        avg_dist = sum(distance_stats) / len(distance_stats)
        print(f"  Average shot distance: {avg_dist:.1f}m")
        if avg_dist > 25:
            print("  ⚠️  Shots from very long distance - AI may need better shot selection")
        
    if power_stats:
        avg_power = sum(power_stats) / len(power_stats)
        print(f"  Average shot power: {avg_power:.1f}")
        
    if on_target_count > 0:
        accuracy = (on_target_count / len(shots)) * 100
        print(f"  Shot accuracy: {accuracy:.1f}% on target")


def analyze_passing_behavior(passes):
    """Analyze passing patterns for realism issues."""
    print("\n=== PASSING BEHAVIOR ANALYSIS ===")
    print(f"Total passes: {len(passes)}")
    
    if not passes:
        print("  ⚠️  No passes detected - major AI issue")
        return
    
    # Count pass types
    under_pressure = sum(1 for _, details in passes if '[UNDER_PRESSURE]' in details)
    progressive = sum(1 for _, details in passes if 'progressive=' in details)
    
    print(f"  Passes under pressure: {under_pressure} ({under_pressure/len(passes)*100:.1f}%)")
    print(f"  Progressive passes: {progressive} ({progressive/len(passes)*100:.1f}%)")
    
    # Analyze progressive distances
    progressive_dists = []
    for _, details in passes:
        prog_match = re.search(r'progressive=([+-][\d.]+)m', details)
        if prog_match:
            progressive_dists.append(float(prog_match.group(1)))
    
    if progressive_dists:
        forward_passes = [d for d in progressive_dists if d > 0]
        backward_passes = [d for d in progressive_dists if d < 0]
        
        print(f"  Forward passes: {len(forward_passes)} (avg: {sum(forward_passes)/len(forward_passes):.1f}m)" if forward_passes else "  Forward passes: 0")
        print(f"  Backward passes: {len(backward_passes)} (avg: {sum(backward_passes)/len(backward_passes):.1f}m)" if backward_passes else "  Backward passes: 0")
        
        if len(backward_passes) > len(forward_passes) * 2:
            print("  ⚠️  Too many backward passes - AI may be too defensive")


def analyze_possession_sequences(possessions):
    """Analyze possession changes and patterns."""
    print("\n=== POSSESSION ANALYSIS ===")
    print(f"Total possession changes: {len(possessions)}")
    
    if len(possessions) < 2:
        print("  ⚠️  Very few possession changes - game may be too one-sided")
        return
    
    # Calculate average possession duration
    possession_times = [t for t, _ in possessions]
    durations = [possession_times[i+1] - possession_times[i] for i in range(len(possession_times)-1)]
    avg_duration = sum(durations) / len(durations)
    
    print(f"  Average possession duration: {avg_duration:.1f}s")
    
    if avg_duration < 3:
        print("  ⚠️  Very short possessions - may indicate poor ball control")
    elif avg_duration > 30:
        print("  ⚠️  Very long possessions - defending team may be too passive")


def analyze_defensive_behavior(tackles):
    """Analyze defensive actions."""
    print("\n=== DEFENSIVE BEHAVIOR ANALYSIS ===")
    print(f"Total tackles: {len(tackles)}")
    
    if not tackles:
        print("  ⚠️  No tackles detected - defenders may be too passive")
        return
    
    # Check tackle distribution
    players_tackling = set()
    for _, details in tackles:
        player_match = re.search(r'Player (\d+)', details)
        if player_match:
            players_tackling.add(player_match.group(1))
    
    print(f"  Players who made tackles: {len(players_tackling)}")


def analyze_player_activity(player_passes, player_shots, player_decisions):
    """Analyze individual player activity levels."""
    print("\n=== PLAYER ACTIVITY ANALYSIS ===")
    
    # Find most/least active players
    if player_passes:
        most_passes = max(player_passes.items(), key=lambda x: x[1])
        least_passes = min(player_passes.items(), key=lambda x: x[1])
        print(f"  Most passes: Player #{most_passes[0]} ({most_passes[1]} passes)")
        print(f"  Least passes: Player #{least_passes[0]} ({least_passes[1]} passes)")
        
        if most_passes[1] > least_passes[1] * 10:
            print("  ⚠️  Huge disparity in pass distribution - some players not involved")
    
    if player_shots:
        print(f"  Players who shot: {len(player_shots)}")
        total_shots = sum(player_shots.values())
        print(f"  Total shots: {total_shots}")
        

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/analyze_match_log.py <log_file_path>")
        print("\nExample:")
        print("  python tools/analyze_match_log.py debug_logs/match_debug_20251117_222236.txt")
        sys.exit(1)
    
    log_path = Path(sys.argv[1])
    
    if not log_path.exists():
        print(f"Error: Log file not found: {log_path}")
        sys.exit(1)
    
    print(f"Analyzing: {log_path.name}")
    print("=" * 60)
    
    data = parse_log_file(log_path)
    
    # Print event summary
    print("\n=== EVENT SUMMARY ===")
    for event_type, count in data['event_types'].most_common(15):
        print(f"  {event_type}: {count}")
    
    # Run specific analyses
    analyze_shooting_behavior(data['shots'])
    analyze_passing_behavior(data['passes'])
    analyze_possession_sequences(data['possessions'])
    analyze_defensive_behavior(data['tackles'])
    analyze_player_activity(data['player_passes'], data['player_shots'], data['player_decisions'])
    
    print("\n" + "=" * 60)
    print("Analysis complete!")


if __name__ == '__main__':
    main()
