import time
import math
from rich.progress import Progress, BarColumn, TextColumn

def fmt_time(seconds: int) -> str:
    """将秒格式化为 M:SS"""
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def main():
    total_time = 30  # 演示歌曲总长 30 秒
    current_time = 0
    step = 0
    print("\n\033[1;35m✦ PLAYER ✦\033[0m")
    print("\033[1;36mTrack:\033[0m 炜煌的星阙 Glorious Metropole")
    print("\033[2mArtist:\033[0m HOYO-MiX")
    print("\033[1m           ⏮️ [b]      ⏸️ [p]      ⏭️ [n]   \033[0m")
    print("\033[2m         ➡️ 顺序播放 [m]  🎚️ 无损flac [c]\033[0m\n")
    progress = Progress(
        TextColumn("\033[33m{task.fields[ct]}\033[0m"),
        BarColumn(bar_width=40, complete_style="bright_cyan", finished_style="bright_cyan"),
        TextColumn("\033[33m{task.fields[tt]}\033[0m"),
        TextColumn("\033[2m{task.description}\033[0m")
    )
    
    try:
        with progress:
            play_task = progress.add_task( 
                '',
                total=total_time, 
                ct=fmt_time(0), 
                tt=fmt_time(total_time)
            )
            last_log_time = -1
            # 模拟播放循环
            while current_time <= total_time:
                progress.update(play_task, completed=current_time, ct=fmt_time(current_time))
                time.sleep(1)
                current_time += 1
                step += 1
                
    except KeyboardInterrupt:
        print("\n\033[1;31mPlayback stopped.\033[0m")

if __name__ == "__main__":
    main()
