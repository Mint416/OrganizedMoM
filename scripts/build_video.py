"""Create a narrated MP4 walkthrough from screenshots of the tested app, using macOS speech."""

import json
import re
import shutil
import subprocess
import textwrap
import wave
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
TARGET_SECONDS = 480
FPS = 24
PAUSE_SECONDS = 1.2
SCENES = [
    (
        "01-overview",
        "The Organized Mom",
        "This is The Organized Mom, a family personal assistant developed from Min Tao's six module project plans. This walkthrough shows screenshots captured from the working application. All family records are synthetic. The default demonstration uses deterministic specialist roles and does not call a language model or connect to real accounts.",
    ),
    (
        "02-sources",
        "Current evidence",
        "The example replays Thursday, August thirteenth, twenty twenty-six. The source view preserves the original soccer notice as superseded. The current BYGA update moves practice to five thirty through seven P M. LingoAce still shows Chinese class from six to seven. Each record retains its identity, revision, and retrieval time.",
    ),
    (
        "03-conflict",
        "A verified conflict",
        "The Information Agent ranks three records using text vectors and latent semantic retrieval. Current-record validation excludes the old notice from the active schedule. Deterministic time checks find a sixty-minute overlap for the same child. The response cites the records and saves an observable case trace. A missing source would keep this check pending.",
    ),
    (
        "04-planning",
        "Bounded alternatives",
        "The Planning Agent compares structured alternatives. A separate Schedule Critic checks evidence, group commitments, and the assumed thirty-minute travel buffer before scoring. The confirmed Friday Chinese make-up resolves the example conflict and scores ninety-seven out of one hundred. The search has explicit branching, depth, and time limits. Unsupported options remain pending or are rejected.",
    ),
    (
        "05-approval-blocked",
        "Parent control",
        "Here I tried to execute the proposed change without approval. The application rejected it. An approval covers the exact action and expires after ten minutes. The server also rejects a changed payload, changed source evidence, or a reused approval. Model commentary and instructions inside a notice cannot grant this permission.",
    ),
    (
        "06a-calendar-verified",
        "A verified local effect",
        "After I approve the exact action, the application writes the change to the local demonstration calendar and reads it back to verify success. The approval and execution remain in the audit trail. This demonstration does not book the LingoAce make-up or update Google Calendar. The original provider records remain unchanged.",
    ),
    (
        "06-memory",
        "Feedback and memory",
        "The simulated outbox creates a family follow-up task. Repeating the notification does not send a duplicate. I can acknowledge the task, mark it done, snooze it, or report a correction. Completed feedback survives a browser reload. The assistant uses persistent SQLite memory to carry this state between visits.",
    ),
    (
        "08-source-failure",
        "Visible failure",
        "Now the LingoAce check fails. The assistant reports that the check is incomplete, keeps the decision pending, and removes the notification action. It does not turn unavailable information into a claim that the schedule is clear. This failure scenario is part of the regression suite.",
    ),
    (
        "09-tournament-rule",
        "Protected commitments",
        "The tournament scenario demonstrates a hard family rule. Skipping a soccer tournament requires a separate parent-provided illness decision. The prototype never infers illness, so it rejects this branch. A numerical score cannot override the rule. Unresolved choices return to the parent.",
    ),
    (
        "10-college-review",
        "Longer-term planning",
        "The High School and College Advisor provides a four-year discussion template. It keeps school-specific requirements and dates unverified until current official sources are supplied. Parent and student review are required. The assistant does not predict admission or replace the school counselor.",
    ),
    (
        "07-reflection",
        "Evaluation and next steps",
        "The Reflection Agent summarizes saved cases, completed tasks, and verified local actions. Forty-one automated tests pass, and the browser walkthrough checks the real interface. These are small synthetic tests, not proof of live service reliability. The GitHub-ready package includes the code, project plan, report, and reproduction scripts. The next stage is an authorized pilot with real accounts and representative evaluation data.",
    ),
    (
        "01-overview",
        "A little perspective, and hopefully hot coffee",
        "Just as I was finishing this project, Meta released Muse, its own personal AI agent. Apparently, my capstone now has a competitor with a slightly bigger budget. So much for my head start! But the timing does make a point: mom or not, we could all use a little help with the mental juggling. A good personal assistant should help us feel more organized and less overwhelmed, so we can give our limited attention to the people and experiences that matter most. And maybe, just once, drink our coffee while it's still hot.",
    ),
]

SCENE_DETAILS = [
    "The problem is familiar: a schedule change arrives in one app, a class reminder arrives in another, and somehow a parent becomes the integration layer. I wanted to reduce that mental work. The application separates six responsibilities: coordination, information retrieval, weekly planning, independent criticism, longer-term student planning, and reflection. These roles exchange structured case records, so I can see where an assumption entered the workflow and which check still needs attention.",
    "Keeping both versions matters because the older message can still look relevant in a search. Relevance alone does not make a record authoritative. The event identifier connects the versions, while revision and status determine which notice applies. The source view also shows the affected child and location. If those details are unclear, the assistant needs clarification before treating the event as a reliable scheduling fact.",
    "Retrieval and conflict detection do different jobs. Retrieval finds useful evidence for the question. The scheduling check compares actual dates and times across the current records in the loaded dataset. It does not rely on a language model to estimate whether two intervals overlap. Here, both activities include six to seven P M. Showing that evidence makes the answer easy for a parent to inspect and correct.",
    "The planner can generate up to four alternatives at a node, retain three states, and search to a depth of three. It also limits expansion count and search time. Those boundaries keep a difficult scheduling question from turning into an endless search. The critic considers feasibility, current evidence, protected commitments, disruption, transportation, and clarity. The thirty-minute travel allowance is a conservative prototype assumption, not a live traffic estimate. A make-up slot must appear in the evidence before the planner can treat it as an available solution.",
    "This is more than a confirmation message on a screen. The server enforces the rule where the effect would happen. A recommendation can be useful without giving the assistant permission to commit the family to it. The preview names the event and proposed times. If the underlying schedule changes before execution, the old approval no longer applies. I have to review a fresh plan rather than unknowingly approve a stale one.",
    "The distinction between a proposed change and a verified result is important. A tool call might fail, return an unexpected response, or succeed without the interface noticing. The local workflow records the effect and checks the saved state before reporting success. In a future live integration, each provider will need its own equivalent verification. Until that exists, the application describes this outcome explicitly as a local demonstration effect.",
    "Memory is what makes the assistant useful beyond a single answer. It records whether a task is pending, acknowledged, completed, snoozed, incorrect, or rescheduled. A snoozed task can produce one reminder after the delay expires. Completing a task stops that reminder path. Quiet hours defer notifications overnight. These controls matter because an assistant that repeatedly tells me what I already know would simply become one more thing to manage.",
    "This is also how I approach a school notice that only contains a protected link. Without authorized access to the details, the item has not been reviewed. The assistant should not invent the missing date or assume that nothing needs doing. The prototype includes separate scenarios for an unknown child and conflicting source records. Each one returns an unresolved state that a parent can recognize and act on.",
    "Family priorities are not always reducible to a convenient numerical score. Group activities and commitments without make-up options deserve protection. Sometimes both commitments are important and the rules do not select a clear winner. That is a legitimate stopping point for automation. The assistant's job is to make the trade-off visible and give the parent enough context to decide.",
    "This role works on a different time horizon from the weekly scheduler. A ninth-grade discussion might begin with interests and course choices, while later years introduce campus research and application milestones. Those are planning topics, not verified requirements for a particular school. The student also needs a voice in the plan. The assistant can organize questions for a counselor meeting without pretending to know what is best for the student's future.",
    "The evaluation includes nine demonstration scenarios. Five authored cases are used for the binary conflict calculation, with four detected conflicts and one correctly clear schedule. That small result supports a regression check, not a broad accuracy claim. The browser test also exercises approval, saved feedback, and the failure path through the actual interface. Before personal use, I still need representative notice extraction tests, complete source synchronization, and live delivery checks. The code and report make those remaining steps explicit so the next phase can build on measured behavior.",
    "",
]
SCENES = [
    (image, title, narration + (" " + detail if detail else ""))
    for (image, title, narration), detail in zip(SCENES, SCENE_DETAILS, strict=True)
]


def timestamp(seconds):
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def main():
    if not shutil.which("say"):
        raise SystemExit(
            "This narration builder requires macOS 'say'. Use the script text to record your own voice on other systems."
        )
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    build = ROOT / "runtime/video-build"
    build.mkdir(parents=True, exist_ok=True)
    output = ROOT / "artifacts"
    timeline, captions, clips, audio_clips, prepared = [], [], [], [], []
    for i, (image, title, narration) in enumerate(SCENES, 1):
        screenshot = output / f"screenshots/{image}.png"
        if not screenshot.exists():
            raise SystemExit(
                f"Missing tested screenshot {screenshot}. Run the browser demo during daytime first."
            )
        text = build / f"scene-{i:02}.txt"
        text.write_text(narration)
        audio = build / f"scene-{i:02}.wav"
        subprocess.run(
            [
                "say",
                "-v",
                "Samantha",
                "-r",
                "160",
                "--file-format=WAVE",
                "--data-format=LEI16@24000",
                "-o",
                str(audio),
                "-f",
                str(text),
            ],
            check=True,
        )
        with wave.open(str(audio)) as stream:
            spoken_duration = stream.getnframes() / stream.getframerate()
        if spoken_duration < 1:
            raise RuntimeError(
                "macOS speech produced empty audio. Allow access to the speech service and rerun; do not deliver a silent video."
            )
        prepared.append((screenshot, title, narration, audio, spoken_duration))
        print(f"Narrated scene {i}/{len(SCENES)}: {title}", flush=True)

    # Allocate an exact frame budget and adjust speech gently to fit the requested eight minutes.
    speech_budget = TARGET_SECONDS - PAUSE_SECONDS * len(prepared)
    total_speech = sum(item[4] for item in prepared)
    tempo = total_speech / speech_budget
    if not 0.8 <= tempo <= 1.25:
        raise RuntimeError(f"Narration needs a content/rate revision to fit naturally; tempo={tempo:.3f}")
    frame_budget = TARGET_SECONDS * FPS
    elapsed_frames = 0
    for i, (screenshot, title, narration, audio, spoken_duration) in enumerate(prepared, 1):
        frames = round((spoken_duration / tempo + PAUSE_SECONDS) * FPS)
        if i == len(prepared):
            frames = frame_budget - elapsed_frames
        duration = frames / FPS
        elapsed = elapsed_frames / FPS
        adjusted_speech = duration - PAUSE_SECONDS
        scene_tempo = spoken_duration / adjusted_speech
        adjusted_audio = build / f"scene-{i:02}-timed.wav"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(audio),
                "-af",
                f"atempo={scene_tempo:.9f},apad,atrim=duration={duration:.9f}",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(adjusted_audio),
            ],
            check=True,
        )
        audio_clips.append(adjusted_audio)
        clip = build / f"scene-{i:02}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-framerate",
                "24",
                "-i",
                str(screenshot),
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x243c36,setsar=1",
                "-frames:v",
                str(frames),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-tune",
                "stillimage",
                "-crf",
                "22",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(clip),
            ],
            check=True,
        )
        clips.append(clip)
        sentences = re.split(r"(?<=[.!?])\s+", narration)
        words = sum(len(s.split()) for s in sentences)
        offset = elapsed
        for sentence in sentences:
            span = adjusted_speech * len(sentence.split()) / words
            captions.append(
                f"{len(captions) + 1}\n{timestamp(offset)} --> {timestamp(offset + span)}\n"
                + "\n".join(textwrap.wrap(sentence, 76))
                + "\n"
            )
            offset += span
        timeline.append(
            {
                "scene": i,
                "title": title,
                "screenshot": str(screenshot.relative_to(ROOT)),
                "start_seconds": round(elapsed, 2),
                "duration_seconds": round(duration, 2),
                "frames": frames,
                "speech_tempo": round(scene_tempo, 5),
                "narration": narration,
            }
        )
        elapsed_frames += frames
        print(f"Rendered scene {i}/{len(SCENES)}: {title}", flush=True)
    concat = build / "clips.txt"
    concat.write_text("\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in clips))
    audio_concat = build / "audio-clips.txt"
    audio_concat.write_text("\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in audio_clips))
    full_audio = build / "eight-minute-narration.wav"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(audio_concat),
            "-c:a",
            "pcm_s16le",
            str(full_audio),
        ],
        check=True,
    )
    subtitles = output / "organized-mom-demo.srt"
    subtitles.write_text("\n".join(captions))
    target = output / "organized-mom-demo.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-i",
            str(full_audio),
            "-i",
            str(subtitles),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map",
            "2:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-movflags",
            "+faststart",
            "-t",
            str(TARGET_SECONDS),
            str(target),
        ],
        check=True,
    )
    report = {
        "file": str(target.relative_to(ROOT)),
        "duration_seconds": TARGET_SECONDS,
        "total_frames": elapsed_frames,
        "width": 1920,
        "height": 1080,
        "narration": "macOS Samantha synthesized voice",
        "format": "Narrated screenshot walkthrough of actual tested UI states, not a continuous screen recording",
        "scenes": timeline,
    }
    (output / "video-manifest.json").write_text(json.dumps(report, indent=2))
    (ROOT / "docs/NARRATION.md").write_text(
        "# Demonstration narration\n\nEight-minute version. Expanded narration in Min's presentation voice. Generated speech uses macOS Samantha. Screenshots come from the tested synthetic app.\n\n"
        + "\n\n".join(f"## {i}. {title}\n\n{narration}" for i, (_, title, narration) in enumerate(SCENES, 1))
        + "\n\n## Closing reference\n\nClosing added September 11, 2026. Meta announced Muse on September 8, 2026: "
        + "[Meta's official announcement](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/). "
        + "The comparison is a personal closing reflection, not a finding that Muse replaces this project's implementation.\n"
    )
    print(f"Created {target.name}, {TARGET_SECONDS} seconds, with narration and optional English subtitles.")


if __name__ == "__main__":
    main()
