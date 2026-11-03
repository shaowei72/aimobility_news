# Crash investigation — 2026-11-03

Yes. Every LLM call in the crashed run went to the local Ollama model (`ollama, qwen3.5:9b` in `output/llm-calls.csv`), and the logs point to the GPU failing while Ollama was using it.

## Timeline for this morning (03 Nov)

| Time | What happened | Source |
|---|---|---|
| 06:50–06:53 | 16 Ollama calls succeed on the GPU, about 5–10 s each | Ollama `server-1.log` |
| 06:53:54 | Windows logs a corrected hardware error on PCIe root port 0:1:0, the slot the graphics card normally uses | System log (WHEA) |
| 06:54:01 | `CUDA error: unknown error` while copying data back from the GPU. Ollama's model process dies and the script logs the HTTP 500 for the "Intelligence Index V5" summary. Windows writes a GPU watchdog report (`WATCHDOG4400`) the same second. | Ollama log, `C:\Windows\LiveKernelReports` |
| 06:54:09 | Ollama restarts but **can't start CUDA** ("invalid argument"), so it runs on the CPU. That's why calls took 57–110 s. | Ollama log |
| 06:57:44–06:58:31 | A second GPU watchdog report (`WATCHDOG4401`). The desktop's window compositor (`dwm.exe`), Windows Terminal and the Microsoft Security app crash, and Windows logs many GPU timeout events (`141`). | Application log |
| 06:58:36 | The script's last Ollama call fails with a 500 | Ollama log |
| 07:03 | Ollama still can't reach the GPU | Ollama log |
| 07:05:39 | Shutdown is started by `winlogon`/SYSTEM. There's no bluescreen for this event; that pattern is typical of a power-button press. | System log, event 1074 |

**What this suggests:** the code didn't crash the computer. It just kept the GPU busy, and the GPU, or its driver or PCIe connection, failed under that load. After the failure the display stopped working properly and the machine was shut down.

## Signs this has happened before

- On 02 Nov at 19:07 there was another GPU watchdog report, and one minute later (19:08) the same kind of SYSTEM-initiated shutdown. The Ollama log from that time has been overwritten, so I can't tell whether Ollama was running.
- On 30 Oct there were three real bluescreens (codes `0x139`, `0x3B` and `0x50`, with dumps in `C:\Windows\Minidump`) and a 13 GB GPU watchdog dump. Ollama had been updated at 12:51 that day, shortly before them.
- Corrected PCIe hardware errors were logged on 30 Oct, 1 Nov, 2 Nov and 3 Nov.

## Likely causes, most to least likely

1. **The NVIDIA driver (32.0.16.2101, dated 19 Oct)** with CUDA 13 on the RTX 5060 Ti. Try a clean reinstall of the current Studio driver, or roll back one version.
2. **The PCIe link or power to the card.** The repeated PCIe errors on the GPU's slot point this way. Reseat the card and check the power connector. If it continues, set the slot to PCIe Gen 4 in the BIOS.
3. **The power supply or heat under sustained load.** Running `nvidia-smi -l 1` during a run would show temperature and power draw. Running a GPU stress test without Ollama would show whether the GPU fails without it.

## To narrow it down

Run the same episode with `--provider openai`. If the machine stays stable, the local GPU work is the trigger. Either way, the code itself is fine.

I didn't open the dump files or confirm the cause.

## Possible follow-ups

- Analyse the 30 Oct minidumps (needs WinDbg).
- Add a guard so the script stops after the first Ollama 500 instead of carrying on.

---

## Second crash — 03 Nov, about 07:42

The same thing happened again during a re-run of MVP 0.3 on Ollama (`qwen3.5:9b`).

| Time | What happened | Source |
|---|---|---|
| 07:31:46 | A restart started from the Start menu by the user. **This was not a crash.** | System log, event 1074 |
| 07:41:00–07:41:57 | Re-run starts. The first 7 calls run normally on the GPU, about 5–10 s each. | `output/llm-calls.csv` |
| 07:42:00 | Windows logs a corrected PCIe hardware error on root port 0:1:0, the GPU's slot. | System log (WHEA, event 17) |
| 07:42:03–08 | Ollama's model process fails with `CUDA error: unknown error` in `ggml_cuda_kernel_launch` and exits with `0xc0000409`. The script records an `error` for **"The Intelligence Index V5 Reshuffles the AI Leaderboard"**. | Ollama `server.log`, Application log (event 1000) |
| 07:42:04 | The Microsoft Security app crashes, as it did in the first crash. | Application log |
| 07:42:16 | Ollama restarts but can't start CUDA (`failed to initialize CUDA: invalid argument`), so it falls back to the CPU. | Ollama `server.log` |
| 07:43:12 | The next call times out with a 500 after 1 minute. | Ollama `server.log` |
| 07:43:18 | Windows is powered off by `winlogon`/SYSTEM, with no bluescreen. This matches the first crash. | System log, event 1074 |

No new GPU watchdog dump was written to `C:\Windows\LiveKernelReports` for this crash.

### Something new

**Both crashes today failed on the same item**, the "Intelligence Index V5" summary. In both runs, the 7–16 calls before it worked. Both times, the PCIe error also appeared a few seconds before the CUDA failure. Two things could explain this:

- **That transcript chunk reliably triggers something on the GPU**, such as a driver or CUDA kernel bug.
- **Timing:** the run reaches that item when the GPU has been under sustained load long enough for the PCIe link, power or heat problem to show up.

The evidence still points to the GPU, driver or PCIe connection rather than the code.

### Tests to tell the explanations apart

1. **Run only the Intelligence Index V5 item on Ollama**, starting from a freshly booted machine. If it fails straight away, the input is triggering a driver bug.
2. **Run the full episode with `--provider openai`.** If the machine stays stable, running models on the local GPU is what sets off the failure.

### Code follow-up

After the first Ollama 500 the script keeps making calls while Ollama is stuck on the CPU. Making it stop at the first Ollama 500 would reduce how long the machine stays in that broken state.
