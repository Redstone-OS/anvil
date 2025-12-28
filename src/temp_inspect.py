
import sys
import asyncio
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from analysis.binary_inspector import BinaryInspector
from core.paths import PathResolver

# Mock PathResolver or simple path
class MockPathResolver:
    @staticmethod
    def windows_to_wsl(path: Path) -> str:
        # Convert D:\... to /mnt/d/...
        p = str(path).replace('\\', '/')
        if p[1] == ':':
            drive = p[0].lower()
            return f"/mnt/{drive}{p[2:]}"
        return p

async def main():
    inspector = BinaryInspector(MockPathResolver())
    kernel_path = Path(r"d:\Github\RedstoneOS\dist\qemu\boot\kernel")
    
    print(f"Inspecting {kernel_path}")
    
    # 1. Check SSE
    violations = await inspector.check_sse_instructions(kernel_path)
    for v in violations:
        print(f"SSE Violation: {v}")
        
    # 2. Key addresses
    # Entry point
    entry = await inspector.get_entry_point(kernel_path)
    print(f"Entry point: 0x{entry:x}" if entry else "Entry point not found")
    
    # 4. Sections
    print("Sections:")
    sections = await inspector.analyze_sections(kernel_path)
    for s in sections:
        print(f"{s.name} Start: 0x{s.address:x} Size: 0x{s.size:x} End: 0x{s.address + s.size:x}")

if __name__ == "__main__":
    asyncio.run(main())
