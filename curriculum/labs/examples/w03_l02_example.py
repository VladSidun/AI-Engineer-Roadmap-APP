import asyncio


async def main() -> None:
    async def name(label: str) -> str:
        await asyncio.sleep(0)
        return label.upper()
    print(await asyncio.gather(name('one'), name('two')))

if __name__ == '__main__':
    asyncio.run(main())
