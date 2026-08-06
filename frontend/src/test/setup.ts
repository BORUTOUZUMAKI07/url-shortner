import "@testing-library/jest-dom/vitest"
import { configure } from "@testing-library/react"
import { server } from "./mocks/server"
import { beforeAll, afterAll, afterEach } from "vitest"

configure({ asyncUtilTimeout: 5000 })

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
