import { createHighlighterCore } from 'shiki/core'
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript'
import python from 'shiki/langs/python.mjs'
import githubDark from 'shiki/themes/github-dark.mjs'

const highlighter = createHighlighterCore({
  langs: [python], themes: [githubDark], engine: createJavaScriptRegexEngine(),
})

export async function pythonTokens(code: string) {
  return (await highlighter).codeToTokensBase(code, { lang: 'python', theme: 'github-dark' })
}
