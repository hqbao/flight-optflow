set(SOURCES 
  main.c 
  mat.c 
  optflow.c 
  image_util.c
)

idf_component_register(SRCS ${SOURCES} INCLUDE_DIRS .)