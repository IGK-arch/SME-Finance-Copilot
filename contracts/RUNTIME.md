# Runtime contract notes

The original handoff schemas and examples are preserved byte-for-byte. Runtime
synthetic execution uses execution-command.schema.json v1: payment plus due time,
cash delta, dependencies, completion predicate and DEMO loan terms. This is an
internal contract and has no relationship to a real banking API.

finance/contracts.py supports the used JSON Schema subset only (types, const/enum,
required/properties/additionalProperties, bounds, date-time, arrays/uniqueItems,
oneOf/allOf/if). No remote references or arbitrary schema execution. Structural
checks are followed by current domain, exact approval and financial checks.

HTTP response: schema_version, request_id, result; errors contain code, safe_message
and retryable. Authenticated membership provides the tenant. Tool responses follow
the supplied tool-result envelope. Submitted commands are not claimed settled.
The plan JSON contains its full actions, quote, independent validation and stress
paths, rather than pretending the handoff metadata envelope alone is executable.
