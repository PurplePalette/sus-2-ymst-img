import argparse
import glob
import os
import re
from dataclasses import dataclass

import sus

from .ytypes import (
    FlickDirection,
    FlickNote,
    GimmickType,
    Hold,
    HoldEighth,
    HoldType,
    NoteType,
    Scratch,
    Sound,
    Split,
    TapNote,
    TapType,
)


@dataclass
class ErrorMessage:
    message: str
    detail: str


class Sus2Ymst:
    def __init__(self, sus_filename: str):
        with open(sus_filename, "r") as file:
            text = file.read()
            self.score: sus.Score = sus.loads(text)
            self.score_text = text
            self.split_ids = [
                int(os.path.splitext(os.path.basename(bundle))[0])
                for bundle in glob.glob("game_splitlane_assets_spliteffects/*.bundle")
                if re.search(r"\d+\.bundle", bundle)
            ]
            self.error_messages = []

    def on_hold_start(self, note: sus.Note):
        for hold in self.score.slides:
            hold_start = hold[0]
            if (
                note.tick == hold_start.tick
                and note.lane == hold_start.lane
                and note.width == hold_start.width
            ):
                return True
        return False

    def on_hold(self, flick_note: sus.Note):
        for hold in self.score.slides:
            hold_start = hold[0]
            hold_end = hold[-1]
            if (
                hold_start.tick < flick_note.tick < hold_end.tick
                and hold_start.lane == flick_note.lane
                and hold_start.width == flick_note.width
            ):
                return True
        return False

    def on_hold_end(self, flick_note: sus.Note):
        for hold in self.score.slides:
            hold_end = hold[-1]
            if (
                flick_note.tick == hold_end.tick
                and flick_note.lane <= hold_end.lane
                and flick_note.lane + flick_note.width >= hold_end.lane + hold_end.width
            ):
                return True
        return False

    def get_direction(self, flick_note: sus.Note):
        for directional in self.score.directionals:
            if (
                directional.tick == flick_note.tick
                and directional.lane == flick_note.lane
                and directional.width == flick_note.width
            ):
                return directional.type
        return None

    def tick_to_sec(self, tick: int) -> float:
        # BPM beats per minute 60秒間に何拍あるか[拍/分]
        # 60秒 / BPM = 1拍の秒数=4分音符の秒数[sec]
        # bar_length、拍数*bar_length=で1小節の長さになる
        # 480[tick]=4分音符の長さ
        # 1[sec/tick] = 4分音符の秒数 / 480

        # BPM変化なし
        if len(self.score.bpms) == 1:
            return (tick / 480) * (60 / self.score.bpms[0][1])
        # BPM変化あり
        bpm_index = 0
        for i, bpm in enumerate(self.score.bpms):
            if tick > bpm[0]:
                bpm_index = i
            else:
                break
        sec = 0
        for i, bpm in enumerate(self.score.bpms[:bpm_index]):
            sec += (
                ((self.score.bpms[i + 1][0] - self.score.bpms[i][0]) / 480)
                * 60
                / self.score.bpms[i][1]
            )
        sec += (
            ((tick - self.score.bpms[bpm_index][0]) / 480)
            * 60
            / self.score.bpms[bpm_index][1]
        )
        return sec

    def get_split(self) -> list[Split]:
        bar_lengths = sorted(self.score.bar_lengths, key=lambda x: x[0])
        high_speed_data_pattern = re.compile(
            r"(?P<barIndex>\d*)'(?P<tickOffset>[0-9]*):(?P<speedRatio>[+-]?(?:\d+\.?\d*|\.\d+))"
        )
        # ハイスピード定義の取得
        high_speed_definition = re.compile(r"#TIL(?P<zz>\d*):(?P<data>.+)")
        high_speed_definitions = high_speed_definition.findall(self.score_text)
        # ハイスピード定義があれば
        if len(high_speed_definitions) == 0:
            return []
        tmp_splits = []
        for s in high_speed_definitions:
            for high_speed in high_speed_data_pattern.findall(s[1]):
                bar_index = int(high_speed[0])
                tick_offset = int(high_speed[1])
                speed_ratio = str(high_speed[2])
                tick = 0
                for i, bar_length in enumerate(bar_lengths):
                    if bar_length[0] <= bar_index:
                        if i != len(bar_lengths) - 1:
                            if bar_lengths[i + 1][0] <= bar_index:
                                tick += (
                                    (bar_lengths[i + 1][0] - bar_length[0])
                                    * bar_length[1]
                                    * 480
                                )
                            else:
                                tick += (
                                    (bar_index - bar_length[0]) * bar_length[1] * 480
                                )
                        else:
                            tick += (bar_index - bar_length[0]) * bar_length[1] * 480
                    else:
                        break
                tick += tick_offset
                gimmick_type = int(speed_ratio.split(".")[0])
                end_flag = False
                if gimmick_type >= 10:
                    gimmick_type /= 10
                    end_flag = True
                if gimmick_type not in range(1, 7):
                    print("gimmick_type must be 1-6")
                    self.error_messages.append(
                        ErrorMessage(
                            "gimmick_typeは1-6で指定してください。",
                            f"bar_index: {bar_index}, tick_offset: {tick_offset}, speed_ratio: {speed_ratio}",
                        )
                    )
                    continue
                split_id = int(speed_ratio.split(".")[1])
                if end_flag:
                    tmp_splits.append(Split(-1, tick, 0, gimmick_type + 10, split_id))
                else:
                    tmp_splits.append(Split(tick, -1, 0, gimmick_type + 10, split_id))
        splits = []
        for i, split1 in enumerate(tmp_splits):
            if split1.end_tick == -1:
                for split2 in tmp_splits[i + 1 :]:
                    if (
                        split2.gimmick_type == split1.gimmick_type
                        and split2.id == split1.id
                    ):
                        if self.check_split(split1.id):
                            splits.append(
                                Split(
                                    split1.tick,
                                    split2.end_tick,
                                    0,
                                    split1.gimmick_type,
                                    split1.id,
                                )
                            )
                        else:
                            print(f"split: {split1.id}はspliteffectsに存在しません。")
                            self.error_messages.append(
                                ErrorMessage(
                                    f"split: {split1.id}はspliteffectsに存在しません。",
                                    f"tick: {split1.tick}, gimmick_type: {split1.gimmick_type}, id: {split1.id}",
                                )
                            )
                        break
                else:
                    print(f"{split1}に対する終了のハイスピードが定義されていません。")
                    self.error_messages.append(
                        ErrorMessage(
                            f"{split1}に対する終了のハイスピードが定義されていません。",
                            f"tick: {split1.tick}, gimmick_type: {split1.gimmick_type}, id: {split1.id}",
                        )
                    )
        return splits

    def check_split(self, split_id: int) -> bool:
        if split_id in self.split_ids:
            return True
        else:
            return False

    def convert(self, lane_flag=False) -> str:
        ticks_per_beat_request = (
            [
                int(request.split()[1])
                for request in self.score.metadata.requests
                if request.startswith("ticks_per_beat")
            ]
            if self.score.metadata.requests
            else []
        )
        ticks_per_beat = ticks_per_beat_request[0]
        if ticks_per_beat != 480:
            print("tick_per_beat must be 480")
            self.error_messages.append(
                ErrorMessage(
                    "tick_per_beatは480である必要があります。",
                    f"tick_per_beat: {ticks_per_beat}",
                )
            )
            return ""

        # スプリットの処理
        splits = self.get_split()

        # ノーツの処理
        tap_notes = []
        scratch_notes = []
        flick_notes = []
        for tap in self.score.taps:
            if tap.type == 1:
                # 通常ノーツ
                tap_notes.append(TapNote(tap.tick, tap.lane, tap.width, TapType.Normal))
            elif tap.type == 2:
                # クリティカルノーツ
                if not self.on_hold_start(tap):
                    # タップクリティカル
                    tap_notes.append(
                        TapNote(tap.tick, tap.lane, tap.width, TapType.Critical)
                    )
            elif tap.type == 3:
                # フリックノーツ
                if self.on_hold(tap):
                    # ホールド中
                    scratch_notes.append(Scratch(tap.tick, tap.lane, tap.width))
                elif not self.on_hold_end(tap):
                    # フリック
                    direction = self.get_direction(tap)
                    if direction is None:
                        direction = FlickDirection.Up
                    flick_notes.append(
                        FlickNote(tap.tick, tap.lane, tap.width, direction)
                    )

        hold_notes = []
        sound_notes = []
        hold_eighth_notes = []
        sus_flick_notes = list(filter(lambda note: note.type == 3, self.score.taps))
        slides = sorted(self.score.slides, key=lambda slide: slide[0].tick)
        for hold in slides:
            start_note = hold[0]
            end_note = hold[-1]
            conntection_note = hold[1:-1]
            hold_type = HoldType.Normal
            gimmick_type = GimmickType.None_
            movement = 0
            scratch_start = False
            # クリティカルかどうか
            for note in self.score.taps:
                if (
                    note.tick == start_note.tick
                    and note.lane == start_note.lane
                    and note.width == start_note.width
                    and note.type == TapType.Critical
                ):
                    hold_type |= HoldType.Critical
                    break
            # スクラッチで始まるかどうか
            for note in sus_flick_notes:
                if (
                    note.tick == start_note.tick
                    and note.lane <= start_note.lane
                    and note.lane + note.width >= start_note.lane + start_note.width
                ):
                    scratch_start = True
            # スクラッチで終わるかどうか
            for note in sus_flick_notes:
                if (
                    note.tick == end_note.tick
                    and note.lane == end_note.lane
                    and note.lane == end_note.lane
                    and note.width == end_note.width
                    # and self.get_direction(note) == FlickDirection.Up
                ):  # 同じ大きさのスクラッチで終わる
                    hold_type |= HoldType.Scratch
                    gimmick_type = GimmickType.None_
                    movement = 0
                    break
                elif (
                    note.tick == end_note.tick
                    and note.lane == end_note.lane
                    # and self.get_direction(note) == FlickDirection.Right
                ):
                    hold_type |= HoldType.Scratch
                    gimmick_type = GimmickType.JumpScratch
                    movement = note.width
                    break
                elif (
                    note.tick == end_note.tick
                    and note.lane + note.width == end_note.lane + end_note.width
                    # and self.get_direction(note) == FlickDirection.Left
                ):
                    hold_type |= HoldType.Scratch
                    gimmick_type = GimmickType.JumpScratch
                    movement = -note.width
                    break

            # 中継点
            if len(conntection_note) > 0:
                if hold_type == HoldType.Normal or hold_type == HoldType.Critical:
                    sound_type = NoteType.Sound
                else:
                    sound_type = NoteType.SoundPurple
                for note in conntection_note:
                    sound_notes.append(
                        Sound(note.tick, note.lane, note.width, sound_type)
                    )

            # 8分判定
            for eighth_tick in range(start_note.tick, end_note.tick, 480 // 2):
                if eighth_tick == start_note.tick:
                    continue
                if eighth_tick >= end_note.tick:
                    break
                hold_eighth_notes.append(
                    HoldEighth(eighth_tick, start_note.lane, start_note.width)
                )

            hold_notes.append(
                Hold(
                    start_note.tick,
                    end_note.tick,
                    start_note.lane,
                    start_note.width,
                    hold_type,
                    gimmick_type,
                    movement,
                    scratch_start,
                )
            )

        all_notes = (
            splits
            + tap_notes
            + scratch_notes
            + flick_notes
            + hold_notes
            + sound_notes
            + hold_eighth_notes
        )

        # ノーツのtick順にソート
        all_notes.sort(key=lambda note: note.tick)

        notation_txt = ""
        for note in all_notes:
            t = self.tick_to_sec(note.tick)
            if lane_flag:
                lane = note.lane + 1
            else:
                lane = note.lane - 2 + 1
            if isinstance(note, TapNote):
                if note.type == TapType.Normal:
                    notation_txt += f"{t:.4f},-1.0,{NoteType.Normal},{lane},{note.width},{GimmickType.None_},{0}\n"
                elif note.type == TapType.Critical:
                    notation_txt += f"{t:.4f},-1.0,{NoteType.Critical},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, Scratch):
                notation_txt += f"{t:.4f},-1.0,{NoteType.Scratch},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, FlickNote):
                notation_txt += f"{t:.4f},-1.0,{NoteType.Flick},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, Hold):
                end_t = self.tick_to_sec(note.end_tick)
                if note.gimmick_type == GimmickType.JumpScratch:
                    gimmick_type = "JumpScratch"
                else:
                    gimmick_type = note.gimmick_type
                if not note.scratch_start:
                    if note.type == HoldType.ScratchCritical:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.ScratchCriticalHoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchCriticalHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    elif note.type == HoldType.Scratch:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.ScratchHoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    elif note.type == HoldType.Critical:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.CriticalHoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.CriticalHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    else:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.HoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.Hold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                else:
                    if note.type == HoldType.ScratchCritical:
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchCriticalHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    elif note.type == HoldType.Scratch:
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
            elif isinstance(note, Sound):
                notation_txt += f"{t:.4f},-1.0,{note.type},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, HoldEighth):
                notation_txt += f"{t:.4f},-1.0,{NoteType.HoldEighth},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, Split):
                end_t = self.tick_to_sec(note.end_tick)
                t += 1.0
                end_t -= 1.0
                if end_t < t:
                    end_t = t + 0.1
                notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.None_},{lane},{0},{note.gimmick_type},{note.id}\n"
        return notation_txt

    def get_error_messages(self) -> list[ErrorMessage]:
        return self.error_messages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert sus to ymst")
    parser.add_argument("sus_file", help="sus file path")
    parser.add_argument(
        "-o",
        "--output_file",
        help="output file path",
        default="notation.txt",
        required=False,
    )
    args = parser.parse_args()

    sus2ymst = Sus2Ymst(args.sus_file)

    notation_txt = sus2ymst.convert()

    with open(args.output_file, "w") as f:
        f.write(notation_txt)
