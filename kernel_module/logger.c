#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/gpio.h>       // Required for the GPIO functions
#include <linux/interrupt.h>  // Required for the IRQ code
#include <linux/kobject.h>    // Using kobjects for the sysfs bindings
#include <linux/time.h>       // Using the clock to measure time between button press
#include <linux/ktime.h>      // Kernel 5.5 needs this for time function calls for kernel space
#include <linux/timekeeping.h>// Kernel 5.5 needs this for time query function calls for kernel space
#include <linux/kobject.h>
#include <linux/fs.h>
#include <asm/uaccess.h>
#define  DEBOUNCE_TIME 200    ///< The default bounce time -- 200ms

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Alan Lin");
MODULE_DESCRIPTION("LKM for button presses on the Attendance Logger");
MODULE_VERSION("0.1");

static unsigned int gpioRedLED = 45;       //Red LED GPIO45 - P8_11
module_param(gpioRedLED, uint, S_IRUGO);
MODULE_PARM_DESC(gpioRedLED, " GPIO red LED number (default=45)");

static unsigned int gpioScrollButton = 44; //Scroll button GPIO44 - P8_12
module_param(gpioScrollButton, uint, S_IRUGO);
MODULE_PARM_DESC(gpioScrollButton, " GPIO scroll button number (default=44)");

static unsigned int gpioGreenLED = 69;     //Green LED GPIO69 - P8_9
module_param(gpioGreenLED, uint, S_IRUGO);
MODULE_PARM_DESC(gpioGreenLED, " GPIO green LED number (default=69)");

static unsigned int gpioUpdateButton = 68; //Update button GPIO68 - P8_10
module_param(gpioUpdateButton, uint, S_IRUGO);
MODULE_PARM_DESC(gpioUpdateButton, " GPIO update button number (default=68)");

static char gpioScrollName[8] = "gpioXXX"; //Null terminated default string just in case
static char gpioUpdateName[8] = "gpioXXX";
static unsigned int irqNumberScroll;
static unsigned int irqNumberUpdate;
static bool         ledRedOn = 0;
static bool         ledGreenOn = 0;
static struct timeval time_ns;
static struct file *f;
static ktime_t ts_end, ts_start, ts_diff;

//Function prototype for the custom IRQ handler functions
static irq_handler_t scroll_irq_handler(unsigned int irq, void *dev_id, struct pt_regs *regs);
static irq_handler_t update_irq_handler(unsigned int irq, void *dev_id, struct pt_regs *regs);

//callback to display how long the button was held for
static ssize_t pressTime_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf){
  return sprintf(buf, "%lu\n", time_ns.tv_sec);
}

//callback to display anything when a button is pressed
static ssize_t activate_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf){
  return sprintf(buf, "triggered");
}

//read only attribute pressTime - how long the button was pressed for
static struct kobj_attribute press_time = __ATTR_RO(pressTime);
static struct kobj_attribute trigger = __ATTR_RO(activate);

static struct attribute *button_attrs[] = {
  &press_time.attr, //how long was the button pressed for?
  &trigger.attr,    //activation file to trigger interrupts
  NULL,
};

static struct attribute_group scroll_attr_group = {
  .name = gpioScrollName,
  .attrs = button_attrs,
};

static struct attribute_group update_attr_group = {
  .name = gpioUpdateName,
  .attrs = button_attrs,
};

static struct kobject *logger;

//Initialization function for module
static int __init logger_init(void){
  int result = 0;

  printk(KERN_INFO "LOGGER: Initializing LKM\n");
  
  sprintf(gpioScrollName, "gpio%d", gpioScrollButton); //create the gpio name for /sys/logger/gpio#
  sprintf(gpioUpdateName, "gpio%d", gpioUpdateButton); //create the gpio name for /sys/logger/gpio#

  //Check if GPIOs are available
  if (!gpio_is_valid(gpioRedLED)) {
    printk(KERN_INFO "LOGGER: invalid GPIOs - red LED\n");
    return -ENODEV;
  } else if (!gpio_is_valid(gpioGreenLED)) {
    printk(KERN_INFO "LOGGER: invalid GPIOs - green LED\n");
    return -ENODEV;
  
  } else if (!gpio_is_valid(gpioUpdateButton)){
    printk(KERN_INFO "LOGGER: invalid GPIOs - Update Button\n");
    return -ENODEV;
  
  } else if (!gpio_is_valid(gpioScrollButton)){
    printk(KERN_INFO "LOGGER: invalid GPIOs - Scroll Button\n");
    return -ENODEV;
  
  }
  
  //create the kobject sysfs entry at /sys/logger
  logger = kobject_create_and_add("logger", kernel_kobj->parent);
  if(!logger){
    printk(KERN_ALERT "LOGGER: failed to create kobject mapping\n");
    return -ENOMEM;
  }
  
  //add the attributes to /sys/logger for the scroll button
  result = sysfs_create_group(logger, &scroll_attr_group);
  if (result) {
    printk(KERN_ALERT "LOGGER: failed to create sysfs group for scroll\n");
    kobject_put(logger); //clean up -- remove the kobject sysfs entry
    return result;
  }
  //add the attributes to /sys/logger for the update button
  result = sysfs_create_group(logger, &update_attr_group);
  if (result) {
    printk(KERN_ALERT "LOGGER: failed to create sysfs group for update\n");
    kobject_put(logger);
    return result;
  }

  ledRedOn = false;
  ledGreenOn = false;

  //red LED
  gpio_request(gpioRedLED, "sysfs");            //request LED
  gpio_direction_output(gpioRedLED, ledRedOn);  //Set as output and off
  gpio_export(gpioRedLED, false);               //Cause gpio45 to appear in /sys/class/gpio

  //green LED
  gpio_request(gpioGreenLED, "sysfs");            //request LED
  gpio_direction_output(gpioGreenLED, ledRedOn);  //Set as output and off
  gpio_export(gpioGreenLED, false);               //Cause gpio69 to appear in /sys/class/gpio

  //Scroll Button
  gpio_request(gpioScrollButton, "sysfs");  //request gpio
  gpio_direction_input(gpioScrollButton);   //Set button gpio as input
  gpio_set_debounce(gpioScrollButton, 200); //Debounce with delay of 200ms
  gpio_export(gpioScrollButton, false);     //Cause gpio44 to appear in /sys/class/gpio

  //Update Button
  gpio_request(gpioUpdateButton, "sysfs");  //request gpio
  gpio_direction_input(gpioUpdateButton);   //Set button gpio as input
  gpio_set_debounce(gpioUpdateButton, 200); //Debounce with delay of 200ms
  gpio_export(gpioUpdateButton, false);     //Cause gpio68 to appear in /sys/class/gpio
  
  //Quick initial test
  printk(KERN_INFO "LOGGER: The button state is currently: %d\n", gpio_get_value(gpioUpdateButton)); 
  printk(KERN_INFO "LOGGER: The button state is currently: %d\n", gpio_get_value(gpioScrollButton));
  
  //Map gpio to irq
  irqNumberScroll = gpio_to_irq(gpioScrollButton);
  irqNumberUpdate = gpio_to_irq(gpioUpdateButton);
  printk(KERN_INFO "LOGGER: The scroll button is mapped to IRQ: %d\n", irqNumberScroll);
  printk(KERN_INFO "LOGGER: The update button is mapped to IRQ: %d\n", irqNumberUpdate);
  
  //request interrupt lines for both buttons
  result = request_irq(irqNumberScroll,                     //The interrupt number requested
                       (irq_handler_t) scroll_irq_handler,  //The pointer to the handler function
                       IRQF_TRIGGER_RISING,                 //Interrupt on rising edge
                       "scroll_gpio_handler",               //Used in /proc/interrupts to identify the owner
                       NULL);                               //The *dev_id for shared interrupt lines

  printk(KERN_INFO "LOGGER: The scroll interrupt request result is: %d\n", result);

  result = request_irq(irqNumberUpdate, 
                       (irq_handler_t) update_irq_handler,
                       IRQF_TRIGGER_RISING,
                       "update_gpio_handler",
                       NULL);

  printk(KERN_INFO "LOGGER: The update interrupt request result is: %d\n", result);
  return 0;
}

static void __exit logger_exit(void){
  kobject_put(logger);
  gpio_set_value(gpioRedLED, 0);
  gpio_set_value(gpioGreenLED, 0);
  gpio_unexport(gpioRedLED);
  gpio_unexport(gpioGreenLED);
  free_irq(irqNumberScroll, NULL);
  free_irq(irqNumberUpdate, NULL);
  gpio_unexport(gpioScrollButton);
  gpio_unexport(gpioUpdateButton);
  gpio_free(gpioRedLED);
  gpio_free(gpioGreenLED);
  gpio_free(gpioScrollButton);
  gpio_free(gpioUpdateButton);
  printk(KERN_INFO "LOGGER: Exiting LKM\n");
}

//irs routine for scroll button
static irq_handler_t scroll_irq_handler(unsigned int irq, void *dev_id, struct pt_regs *regs){
  ts_start = ktime_get_real();
  while (gpio_get_value(gpioScrollButton)){
    gpio_set_value(gpioGreenLED, 1);
    if (!gpio_get_value(gpioScrollButton)){
     break;
    }
  }
  ts_end = ktime_get_real();
  ts_diff = ktime_sub(ts_end, ts_start);
  time_ns = ktime_to_timeval(ts_diff);
  gpio_set_value(gpioGreenLED, 0);     
  printk(KERN_INFO "LOGGER: Scroll Button was pressed!\n");
  printk(KERN_INFO "LOGGER: The button was held for %lu seconds\n", time_ns.tv_sec);
  f = filp_open("/sys/logger/gpio44/activate", O_RDONLY, 0);
  if (f == NULL)
    printk(KERN_ALERT "filp_open error! \n");
  filp_close(f, NULL);
  return (irq_handler_t) IRQ_HANDLED;
}

//irs routine for update button
static irq_handler_t update_irq_handler(unsigned int irq, void *dev_id, struct pt_regs *regs){
  ts_start = ktime_get_real();
  while (gpio_get_value(gpioUpdateButton)){
    gpio_set_value(gpioGreenLED, 1);
    if (!gpio_get_value(gpioUpdateButton)){
     break;
    }
  }
  ts_end = ktime_get_real();
  ts_diff = ktime_sub(ts_end, ts_start);
  time_ns = ktime_to_timeval(ts_diff);
  gpio_set_value(gpioGreenLED, 0);     
  printk(KERN_INFO "LOGGER: Update Button was pressed!\n");
  printk(KERN_INFO "LOGGER: The button was held for %lu seconds\n", time_ns.tv_sec);
  f = filp_open("/sys/logger/gpio68/activate", O_RDONLY, 0);
  if (f == NULL)
    printk(KERN_ALERT "filp_open error! \n");
  filp_close(f, NULL);
  return (irq_handler_t) IRQ_HANDLED;
}

//These are mandatory to identify the initialization function and cleanup
//functions
module_init(logger_init);
module_exit(logger_exit);
