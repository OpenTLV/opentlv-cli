# Run from a build directory: cmake -DCLI=/path/to/otlv -P /path/to/tools/cli/examples.cmake
cmake_minimum_required(VERSION 3.16)

function(run_cli expected)
    execute_process(COMMAND "${CLI}" ${ARGN} RESULT_VARIABLE result
        OUTPUT_VARIABLE output ERROR_VARIABLE error)
    string(STRIP "${output}" output)
    if(NOT result EQUAL 0 OR NOT error STREQUAL "" OR NOT output STREQUAL expected)
        message(FATAL_ERROR "${ARGN}: ${result}\n${output}\n${error}\nExpected: ${expected}")
    endif()
endfunction()

# Same Fixed-format Hello, world! round trip as the multi-language quick-start.
run_cli("010D48656C6C6F2C20776F726C6421" encode --format fixed --tag 01 --value 48656C6C6F2C20776F726C6421)
run_cli("offset=0 tag=01 length=13 value=48656C6C6F2C20776F726C6421" dump --format fixed --hex 010D48656C6C6F2C20776F726C6421 --no-color)

# Same nested bytes as C++ parse.cpp, write.cpp and query.cpp.
set(wire "6F0A8403414243A503500101")
set(model [=[{"schema":"opentlv.tlv","version":1,"format":"ber","elements":[{"tag":"6F","length_mode":"definite","children":[{"tag":"84","value":"414243"},{"tag":"A5","length_mode":"definite","children":[{"tag":"50","value":"01"}]}]}]}]=])
run_cli("${model}" decode --format ber --hex "${wire}")
run_cli("01" query 6F/A5/50 --format ber --hex "${wire}" --value)

# Write the decoded model in the build directory, then regenerate the exact wire bytes.
set(json "${CMAKE_CURRENT_BINARY_DIR}/cpp-example.json")
file(WRITE "${json}" "${model}\n")
run_cli("${wire}" encode --format ber --input "${json}")
